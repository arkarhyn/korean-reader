"""Stage 7 Phase A: turn episode transcripts into speaker-labeled, part-split reader input.

    python prep.py cues NN            -> work/NN.cues.txt (numbered cue list for the labeling pass)
    python prep.py assemble NN [...]  -> prepared/NN_slug.json from labels/NN.txt
    uv run --project ../../../server python prep.py rank [--db PATH]
                                      -> coverage.json (per episode, and per part where prepared)

Labels file format (labels/NN.txt), written by a Claude Code labeling pass:
    # part 1 | 배달 앱 이야기 | Talking about delivery apps
    0-3 디디
    4 태웅
    5-9 태웅?          (trailing ? = speaker uncertain)
    # part 2 | ... | ...
Every cue index must be covered exactly once, in order. The Korean text is never
rewritten: turns are assembled verbatim from the subtitle cues.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EPISODES = os.path.join(HERE, "episodes")
WORK = os.path.join(HERE, "work")
LABELS = os.path.join(HERE, "labels")
PREPARED = os.path.join(HERE, "prepared")


def episode_path(nn):
    hits = glob.glob(os.path.join(EPISODES, f"{int(nn):02d}_*.json"))
    if not hits:
        sys.exit(f"no episode {nn}")
    return hits[0]


def load(nn):
    return json.load(open(episode_path(nn), encoding="utf-8"))


def ts(ms):
    s = ms // 1000
    return f"{s // 60:02d}:{s % 60:02d}"


def cmd_cues(args):
    os.makedirs(WORK, exist_ok=True)
    for nn in args.nn:
        ep = load(nn)
        out = os.path.join(WORK, f"{int(nn):02d}.cues.txt")
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"# {ep['title']}\n# {len(ep['segments'])} cues; format: idx [mm:ss] ko || en\n")
            for i, s in enumerate(ep["segments"]):
                f.write(f"{i} [{ts(s['start_ms'])}] {s['ko']} || {s.get('en', '')}\n")
        print(out)


LABEL_RE = re.compile(r"^(\d+)(?:-(\d+))?\s+(\S+?)(\?)?$")
PART_RE = re.compile(r"^#\s*part\s+(\d+)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*$")


def parse_labels(path, n_cues):
    parts, expect = [], 0
    for ln, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        if m := PART_RE.match(line):
            parts.append({"part": int(m[1]), "title_ko": m[2], "title_en": m[3], "runs": []})
            continue
        if line.startswith("#"):
            continue
        m = LABEL_RE.match(line)
        if not m or not parts:
            sys.exit(f"{path}:{ln}: can't parse {line!r}")
        a, b = int(m[1]), int(m[2] or m[1])
        if a != expect or b < a:
            sys.exit(f"{path}:{ln}: expected run starting at {expect}, got {a}-{b}")
        parts[-1]["runs"].append((a, b, m[3], bool(m[4])))
        expect = b + 1
    if expect != n_cues:
        sys.exit(f"{path}: labels cover 0-{expect - 1}, episode has {n_cues} cues")
    return parts


def cmd_assemble(args):
    os.makedirs(PREPARED, exist_ok=True)
    for nn in args.nn:
        ep = load(nn)
        segs = ep["segments"]
        parts = parse_labels(os.path.join(LABELS, f"{int(nn):02d}.txt"), len(segs))
        out_parts = []
        for p in parts:
            turns = []
            for a, b, speaker, unsure in p["runs"]:
                # Adjacent runs with the same speaker are one turn.
                if turns and turns[-1]["speaker"] == speaker and turns[-1].get("uncertain", False) == unsure:
                    turn = turns[-1]
                else:
                    turn = {"speaker": speaker, "lines": []}
                    if unsure:
                        turn["uncertain"] = True
                    turns.append(turn)
                for s in segs[a:b + 1]:
                    turn["lines"].append({k: s[k] for k in ("start_ms", "end_ms", "ko", "en") if k in s})
            for t in turns:
                t["start_ms"], t["end_ms"] = t["lines"][0]["start_ms"], t["lines"][-1]["end_ms"]
                t["ko"] = "\n".join(l["ko"] for l in t["lines"])
                t["en"] = " ".join(l["en"] for l in t["lines"] if l.get("en"))
            out_parts.append({
                "part": p["part"], "title_ko": p["title_ko"], "title_en": p["title_en"],
                "start_ms": turns[0]["start_ms"], "end_ms": turns[-1]["end_ms"],
                "hangul_chars": sum(len(re.findall(r"[가-힣]", t["ko"])) for t in turns),
                "turns": turns,
            })
        name = os.path.basename(episode_path(nn))
        doc = {k: ep[k] for k in ("id", "title", "url", "upload_date", "duration_s", "order", "show_no", "sources")}
        doc["speakers"] = sorted({t["speaker"] for p in out_parts for t in p["turns"]})
        doc["parts"] = out_parts
        with open(os.path.join(PREPARED, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
        md = [f"# {ep['title']}", "", f"{ep['url']}", ""]
        for p in out_parts:
            md += [f"## Part {p['part']}: {p['title_ko']} ({p['title_en']})",
                   f"`{ts(p['start_ms'])}–{ts(p['end_ms'])}` · {p['hangul_chars']} hangul", ""]
            for t in p["turns"]:
                who = t["speaker"] + ("?" if t.get("uncertain") else "")
                md.append(f"**{who}:** " + "  \n".join(
                    f"{l['ko']} <sub>{l.get('en', '')}</sub>" for l in t["lines"]))
                md.append("")
        with open(os.path.join(PREPARED, name[:-5] + ".md"), "w", encoding="utf-8") as f:
            f.write("\n".join(md))
        n_turns = sum(len(p["turns"]) for p in out_parts)
        unsure = sum(1 for p in out_parts for t in p["turns"] if t.get("uncertain"))
        print(f"{name}: {len(out_parts)} parts, {n_turns} turns ({unsure} uncertain), speakers {doc['speakers']}")
        for p in out_parts:
            print(f"  part {p['part']:>2} {ts(p['start_ms'])}-{ts(p['end_ms'])} "
                  f"{p['hangul_chars']:>5} hangul  {p['title_en']}")


def cmd_rank(args):
    if args.db:
        os.environ["DATABASE_PATH"] = args.db
    sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "server")))
    from app.analyzer import analyze  # noqa: E402
    from app.coverage import coverage  # noqa: E402
    from app.db import make_engine, make_sessionmaker  # noqa: E402
    from app.ingest import known_keys  # noqa: E402
    from app.db.models import Lexeme  # noqa: E402
    from sqlalchemy import select  # noqa: E402

    sys.stdout.reconfigure(encoding="utf-8")
    with make_sessionmaker(make_engine())() as session:
        known = known_keys(session)
        if args.assume:  # what-if: treat a word set's keys as known
            items = json.load(open(args.assume, encoding="utf-8"))["set"]["items"]
            known = known | {tuple(k.rsplit("/", 1)) for it in items for k in it["keys"]}
        ranks = dict(((l, p), (r, g)) for l, p, r, g in session.execute(
            select(Lexeme.lemma, Lexeme.pos, Lexeme.freq_rank, Lexeme.gloss_en)))

    names = {"디디", "태웅", "정태웅", "태웅쌤"}

    corpus_counts, corpus_spread = {}, {}

    def report(texts, tally=False):
        toks = [t for x in texts for t in analyze(x)]
        counts = {}
        for t in toks:
            if t.kind == "content" and t.key not in known and t.lemma not in names:
                counts[t.key] = counts.get(t.key, 0) + 1
        if tally:
            for k, n in counts.items():
                corpus_counts[k] = corpus_counts.get(k, 0) + n
                corpus_spread[k] = corpus_spread.get(k, 0) + 1
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:args.top]
        return {
            "coverage": round(coverage(toks, known, names), 4),
            "content_tokens": sum(1 for t in toks if t.kind == "content"),
            "unknown_lemmas": len(counts),
            "top_unknown": [{"lemma": l, "pos": p, "count": n, "freq_rank": ranks.get((l, p), (None, ""))[0],
                             "gloss": ranks.get((l, p), (None, ""))[1]} for (l, p), n in top],
        }

    index = json.load(open(os.path.join(HERE, "index.json"), encoding="utf-8"))["episodes"]
    results = []
    for e in index:
        if e["sources"]["ko"] != "manual":
            continue
        ep = json.load(open(os.path.join(HERE, e["file"]), encoding="utf-8"))
        r = {"order": e["order"], "file": e["file"], "title": e["title"]}
        r.update(report([s["ko"] for s in ep["segments"]], tally=True))
        prepared = os.path.join(PREPARED, os.path.basename(e["file"]))
        if os.path.exists(prepared):
            prep = json.load(open(prepared, encoding="utf-8"))
            r["parts"] = [{"part": p["part"], "title_en": p["title_en"],
                           **report([t["ko"] for t in p["turns"]])} for p in prep["parts"]]
        results.append(r)
        print(f"{e['order']:02d} {r['coverage']:.1%}  {r['unknown_lemmas']:>4} unknown lemmas  {e['file']}")
        for p in r.get("parts", []):
            print(f"     part {p['part']:>2} {p['coverage']:.1%}  {p['title_en']}")
    results.sort(key=lambda r: -r["coverage"])
    # Words unknown to you that recur across the most episodes: the best mining / pre-teach list.
    corpus_top = [{"lemma": l, "pos": p, "count": n, "episodes": corpus_spread[(l, p)],
                   "freq_rank": ranks.get((l, p), (None, ""))[0], "gloss": ranks.get((l, p), (None, ""))[1]}
                  for (l, p), n in sorted(corpus_counts.items(),
                                          key=lambda kv: (-corpus_spread[kv[0]], -kv[1]))[:200]]
    print("\nTop recurring unknowns (episodes, count):")
    print("  " + ", ".join(f"{u['lemma']}({u['episodes']},{u['count']})" for u in corpus_top[:40]))
    if args.assume:
        return
    with open(os.path.join(HERE, "coverage.json"), "w", encoding="utf-8") as f:
        json.dump({"known_words": len(known), "episodes": results, "corpus_top_unknown": corpus_top},
                  f, ensure_ascii=False, indent=1)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("cues", "assemble"):
        p = sub.add_parser(name)
        p.add_argument("nn", nargs="+")
    p = sub.add_parser("rank")
    p.add_argument("--db", help="SQLite path (default: server's DATABASE_PATH)")
    p.add_argument("--top", type=int, default=30)
    p.add_argument("--assume", help="word_set.json whose keys count as known (what-if; writes no coverage.json)")
    a = ap.parse_args()
    {"cues": cmd_cues, "assemble": cmd_assemble, "rank": cmd_rank}[a.cmd](a)


if __name__ == "__main__":
    main()
