"""Normalize raw yt-dlp json3 subtitles into per-episode JSON + Markdown.

Run from anywhere: `python corpus/podcasts/didi-taewoong/build.py`
Inputs:  raw/*.json3 (subtitles), raw/*.info.json (metadata, optional once index.json exists)
Outputs: episodes/NN_slug.json, episodes/NN_slug.md, index.json
"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "episodes")
HANGUL = re.compile(r"[가-힣]")


def events(path):
    d = json.load(open(path, encoding="utf-8"))
    for e in d.get("events", []):
        if "segs" not in e or e.get("aAppend"):
            continue
        text = "".join(s.get("utf8", "") for s in e["segs"]).strip()
        if text:
            start = e.get("tStartMs", 0)
            yield start, start + e.get("dDurationMs", 0), text


def find(vid, langs):
    for lang in langs:
        hits = glob.glob(os.path.join(RAW, f"*{vid}.{lang}.json3"))
        if hits:
            return lang, hits[0]
    return None, None


def english_only(text):
    # Manual "en" tracks on this channel are bilingual: Korean line, then English line.
    return " ".join(l.strip() for l in text.split("\n") if l.strip() and not HANGUL.search(l))


def korean_only(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    ko = [l for l in lines if HANGUL.search(l)]
    return " ".join(ko or lines)


SLUG_OVERRIDES = {
    "C3LVWu8NDcA": "rainy-season",
    "PIQW9jtKDbc": "meetup-in-seoul-special",
    "8HRs3EO0Jh8": "hamburger",
    "CR1LlqpvCsQ": "delivery",
}


def slugify(title, vid):
    if vid in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[vid]
    m = re.findall(r"\(([^()]*[A-Za-z][^()]*)\)", title)
    eng = m[-1] if m else re.sub(r"[^\x00-\x7f]", " ", title)
    s = re.sub(r"[^a-z0-9]+", "-", eng.lower()).strip("-")
    s = re.sub(r"^(eng-sub|sub|video-ver)-?", "", s)
    return s[:50].strip("-") or vid


def ts(ms):
    s = ms // 1000
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def load_meta():
    idx_path = os.path.join(HERE, "index.json")
    meta = {}
    if os.path.exists(idx_path):
        for ep in json.load(open(idx_path, encoding="utf-8"))["episodes"]:
            meta[ep["id"]] = ep
    for f in glob.glob(os.path.join(RAW, "*.info.json")):
        d = json.load(open(f, encoding="utf-8"))
        fresh = {
            "playlist_index": d.get("playlist_index"),
            "id": d["id"],
            "title": d.get("title"),
            "url": f"https://www.youtube.com/watch?v={d['id']}",
            "channel": d.get("channel"),
            "upload_date": d.get("upload_date"),
            "duration_s": d.get("duration"),
            "description": d.get("description"),
        }
        meta.setdefault(d["id"], {}).update({k: v for k, v in fresh.items() if v is not None})
    # raw/playlist.txt ("<index> <id>" per line, written by fetch.py) is authoritative
    # for positions, which shift as new episodes are added at the top.
    order_path = os.path.join(RAW, "playlist.txt")
    if os.path.exists(order_path):
        for line in open(order_path, encoding="utf-8"):
            parts = line.split()
            if len(parts) == 2 and parts[1] in meta:
                meta[parts[1]]["playlist_index"] = int(parts[0])
    return meta


def build(m):
    vid = m["id"]
    ko_lang, ko_path = find(vid, ["ko", "ko-orig"])
    en_lang, en_path = find(vid, ["en", "en-US"])
    ko_events = list(events(ko_path)) if ko_path else []
    en_events = [(s, e, english_only(t)) for s, e, t in events(en_path)] if en_path else []

    segments = []
    for s, e, t in ko_events:
        speaker_change = t.startswith(">>")
        t = korean_only(t.lstrip("> ").strip())
        if not t:
            continue
        seg = {"start_ms": s, "end_ms": e, "ko": t}
        if speaker_change:
            seg["speaker_change"] = True
        segments.append(seg)

    # Align English cues to Korean segments by cue midpoint.
    if en_events and segments:
        starts = [seg["start_ms"] for seg in segments]
        buckets = [[] for _ in segments]
        j = 0
        for s, e, t in en_events:
            if not t:
                continue
            mid = (s + e) // 2
            while j + 1 < len(starts) and starts[j + 1] <= mid:
                j += 1
            while j > 0 and starts[j] > mid:
                j -= 1
            buckets[j].append(t)
        for seg, b in zip(segments, buckets):
            if b:
                seg["en"] = " ".join(b)

    src = {"ko": "manual" if ko_lang == "ko" else ("auto" if ko_lang else None),
           "en": "manual" if en_lang else None}
    return segments, src


def main():
    os.makedirs(OUT, exist_ok=True)
    meta = load_meta()
    index = []
    total = len(meta)
    # Playlist is newest-first; number files oldest-first. The show's own ♯ numbers
    # have a duplicate (♯30) and a gap (♯16), so they're kept only as `show_no`.
    for m in sorted(meta.values(), key=lambda m: -m["playlist_index"]):
        segments, src = build(m)
        m["order"] = total + 1 - m["playlist_index"]
        no = re.search(r"♯(\d+)", m["title"])
        m["show_no"] = int(no.group(1)) if no else None
        name = f"{m['order']:02d}_{slugify(m['title'], m['id'])}"
        ko_chars = sum(len(HANGUL.findall(s["ko"])) for s in segments)
        entry = {k: v for k, v in m.items() if k != "description"}
        entry.update({"file": f"episodes/{name}.json", "sources": src,
                      "segments": len(segments), "hangul_chars": ko_chars})
        entry["description"] = m.get("description")
        index.append(entry)

        doc = {k: v for k, v in entry.items() if k not in ("file",)}
        doc["segments"] = segments
        with open(os.path.join(OUT, name + ".json"), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)

        lines = [f"# {m['title']}", "",
                 f"- URL: {m['url']}",
                 f"- Uploaded: {m['upload_date']}  ·  Length: {ts((m['duration_s'] or 0) * 1000)}",
                 f"- Korean subs: {src['ko']}  ·  English subs: {src['en'] or 'none'}", ""]
        if src["ko"] == "auto":
            lines += ["> Korean text is YouTube auto-captioning: expect misheard words "
                      "and no punctuation. `—` marks a speaker change.", ""]
        for s in segments:
            mark = "— " if s.get("speaker_change") else ""
            lines.append(f"`{ts(s['start_ms'])}` {mark}{s['ko']}  ")
            if s.get("en"):
                lines.append(f"<sub>{s['en']}</sub>")
            lines.append("")
        with open(os.path.join(OUT, name + ".md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    with open(os.path.join(HERE, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"show": "디디와 정태웅의 한국생활 요모조모 (Didi & Taewoong, Korean Life Bit by Bit)",
                   "playlist": "https://www.youtube.com/playlist?list=PLekI352WvEBPAgoMY2dl5_5Ml37M9nSLZ",
                   "episodes": index}, f, ensure_ascii=False, indent=1)
    for e in index:
        print(f"{e['order']:02d} #{e['show_no']} ko={e['sources']['ko']:<6} en={str(e['sources']['en']):<6} "
              f"segs={e['segments']:<5} hangul={e['hangul_chars']:<6} {e['file']}")


if __name__ == "__main__":
    main()
