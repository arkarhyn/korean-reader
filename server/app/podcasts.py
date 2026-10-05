"""Podcast parts (Stage 7): prepared transcripts -> `podcast` series episodes.

Input is Phase A output in corpus/podcasts/<show>/prepared/NN_slug.json (parts ->
speaker turns -> timed subtitle lines, see corpus/podcasts/didi-taewoong/README.md).
Each part becomes one episode `pod-<show>-<NN>-p<k>`; each turn one paragraph whose
`ko` is its lines joined by newlines and whose `meta` keeps the speaker and timings.
"""

import json
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .analyzer import proper_nouns
from .config import REPO_ROOT
from .content.schema import Episode as EpisodeDoc
from .db.models import Episode, Event, Lexeme
from .ingest import known_keys

CORPUS = REPO_ROOT / "corpus" / "podcasts"
SHOWS = {"didi-taewoong": {"key": "dt", "title_ko": "디디와 정태웅의 한국생활 요모조모",
                           "title_en": "Didi & Taewoong: Korean Life, Bit by Bit"}}
BANMAL_EPISODES = {("didi-taewoong", 16)}  # the 반말-mode special


def part_id(show: str, order: int, part: int) -> str:
    return f"pod-{SHOWS[show]['key']}-{order:02d}-p{part}"


def turn_paragraph(turn: dict) -> dict:
    ko, lines = "", []
    for ln in turn["lines"]:
        if ko:
            ko += "\n"
        lines.append({"s": len(ko), "start_ms": ln["start_ms"], "end_ms": ln["end_ms"], "en": ln.get("en", "")})
        ko += ln["ko"]
    meta = {"speaker": turn["speaker"], "start_ms": turn["start_ms"], "end_ms": turn["end_ms"], "lines": lines}
    if turn.get("uncertain"):
        meta["uncertain"] = True
    return {"ko": ko, "en": turn.get("en", ""), "meta": meta}


def part_docs(show: str, prepared: dict) -> list[EpisodeDoc]:
    """One EpisodeDoc per part of a prepared episode."""
    video_id = prepared["url"].rsplit("v=", 1)[-1]
    register = ["banmal"] if (show, prepared["order"]) in BANMAL_EPISODES else ["haeyo"]
    n = len(prepared["parts"])
    return [EpisodeDoc(
        id=part_id(show, prepared["order"], p["part"]),
        series="podcast",
        title_ko=p["title_ko"],
        title_en=p["title_en"],
        register_tags=register,
        source=f"youtube:{video_id}",
        summary=prepared["title"],
        media={"kind": "youtube", "video_id": video_id, "start_ms": p["start_ms"], "end_ms": p["end_ms"],
               "show": show, "order": prepared["order"], "show_episode": prepared.get("show_no"),
               "episode_title": prepared["title"], "part": p["part"], "parts": n},
        paragraphs=[turn_paragraph(t) for t in p["turns"]],
    ) for p in prepared["parts"]]


def prepared_files(show: str, orders: list[int] | None = None, root: Path = CORPUS) -> Iterator[Path]:
    for path in sorted((root / show / "prepared").glob("*.json")):
        if orders is None or int(path.name[:2]) in orders:
            yield path


def load_prepared(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def live_coverage(session: Session, parts: list[Episode]) -> dict[str, float | None]:
    """Coverage of each part against the words known now (SPEC 7, as at ingest: tag aliases,
    names count as known). Stored `episode.coverage` is only a snapshot from ingest time."""
    known = known_keys(session)
    names = proper_nouns()
    lex_ids = {t["lex"] for ep in parts for p in ep.paragraphs for t in p.tokens if "lex" in t}
    rows = session.execute(select(Lexeme.id, Lexeme.lemma, Lexeme.pos).where(Lexeme.id.in_(lex_ids))) if lex_ids else []
    is_known = {i: (lemma, pos) in known or (pos == "NNP" and lemma in names) for i, lemma, pos in rows}
    out = {}
    for ep in parts:
        lexes = [t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t]
        out[ep.id] = sum(is_known.get(i, False) for i in lexes) / len(lexes) if lexes else ep.coverage
    return out


def podcasts_out(session: Session) -> list[dict]:
    """Shows -> episodes -> parts for the Listen tab (published parts only), coverage computed live."""
    parts = session.scalars(select(Episode).where(Episode.series == "podcast", Episode.status == "published")
                            .options(selectinload(Episode.paragraphs))).all()
    coverage = live_coverage(session, parts)
    primers = {ep.source.removeprefix("primer:"): ep for ep in session.scalars(
        select(Episode).where(Episode.series == "primer", Episode.source.like("primer:%")))}
    requested = {e.payload.get("episode_id") for e in session.scalars(
        select(Event).where(Event.type == "primer_request"))}
    shows: dict[str, dict] = {}
    for ep in parts:
        m = ep.media or {}
        show = shows.setdefault(m.get("show", "?"), {"id": m.get("show", "?"), "episodes": {},
                                                    **{k: v for k, v in SHOWS.get(m.get("show"), {}).items()
                                                       if k != "key"}})
        e = show["episodes"].setdefault(m.get("order"), {
            "order": m.get("order"), "show_episode": m.get("show_episode"), "title": m.get("episode_title"),
            "video_id": m.get("video_id"), "register_tags": ep.register_tags, "parts": []})
        primer = primers.get(ep.id)
        e["parts"].append({
            "id": ep.id, "part": m.get("part"), "title_ko": ep.title_ko, "title_en": ep.title_en,
            "start_ms": m.get("start_ms"), "end_ms": m.get("end_ms"), "coverage": coverage[ep.id],
            "primer": ("published" if primer is not None and primer.status == "published"
                       else "requested" if ep.id in requested else None),
            "primer_id": primer.id if primer is not None and primer.status == "published" else None,
        })
    out = []
    for show in shows.values():
        eps = sorted(show.pop("episodes").values(), key=lambda e: e["order"] or 0)
        for e in eps:
            e["parts"].sort(key=lambda p: p["part"] or 0)
        out.append({**show, "episodes": eps})
    return out
