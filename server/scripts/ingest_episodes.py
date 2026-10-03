"""Ingest episode JSON into the DB.

    uv run python scripts/ingest_episodes.py [paths...] [--publish] [--seed] [--offline] [--cache-only]

Paths default to every JSON under content/episodes/. --seed loads grammar
points and flagged vocab first. --offline skips krdict (glosses stay "none").
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import CONTENT_DIR, KRDICT_API_KEY, KRDICT_CACHE_PATH  # noqa: E402
from app.content.schema import load_episode  # noqa: E402
from app.db import make_engine, make_sessionmaker  # noqa: E402
from app.db.migrate import upgrade  # noqa: E402
from app.ingest import ingest_episode, seed  # noqa: E402
from app.krdict.cache import KrdictCache  # noqa: E402
from app.krdict.client import KrdictClient  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--publish", action="store_true", help="set status=published")
    ap.add_argument("--seed", action="store_true", help="load grammar points + flagged vocab first")
    ap.add_argument("--offline", action="store_true", help="no krdict lookups")
    ap.add_argument("--cache-only", action="store_true", help="krdict glosses from the local cache only")
    args = ap.parse_args()

    paths = args.paths or sorted((CONTENT_DIR / "episodes").rglob("*.json"))
    client = None if args.offline else KrdictClient(KRDICT_API_KEY, KrdictCache(KRDICT_CACHE_PATH))
    lookup = None if client is None else client.lookup_cached if args.cache_only else client.lookup

    engine = make_engine()
    upgrade(engine)
    with make_sessionmaker(engine)() as session:
        if args.seed:
            seed(session, lookup)
            print("seeded grammar points + flagged vocab")
        for path in paths:
            r = ingest_episode(session, load_episode(path), lookup, publish=args.publish)
            print(f"{r.episode_id}: coverage {r.coverage:.1%} over {r.content_tokens} content tokens, "
                  f"{len(r.new_lexemes)} new lexemes")
            for lemma, pos in r.missing_gloss:
                print(f"  no gloss: {lemma} ({pos})")
        session.commit()


if __name__ == "__main__":
    main()
