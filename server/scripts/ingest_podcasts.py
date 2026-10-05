"""Ingest prepared podcast transcripts as hidden `podcast` series episodes (one per part).

    uv run python scripts/ingest_podcasts.py [NN ...] [--show didi-taewoong] [--publish] [--live | --offline]

Reads corpus/podcasts/<show>/prepared/NN_slug.json (Phase A output; all of them by
default). Glosses as in ingest_episodes.py. Re-running replaces the parts in place.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import KRDICT_API_KEY, KRDICT_CACHE_PATH, KRDICT_LOCAL_PATH  # noqa: E402
from app.db import make_engine, make_sessionmaker  # noqa: E402
from app.db.migrate import upgrade  # noqa: E402
from app.ingest import first_of, ingest_episode  # noqa: E402
from app.krdict.cache import KrdictCache  # noqa: E402
from app.krdict.client import KrdictClient  # noqa: E402
from app.krdict.local import LocalDict  # noqa: E402
from app.podcasts import load_prepared, part_docs, prepared_files  # noqa: E402
from app.srs import derive  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("episodes", nargs="*", type=int, help="episode numbers (NN in the file name)")
    ap.add_argument("--show", default="didi-taewoong")
    ap.add_argument("--publish", action="store_true", help="set status=published")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--live", action="store_true", help="also query the krdict API for missing glosses")
    src.add_argument("--offline", action="store_true", help="no gloss lookups")
    args = ap.parse_args()

    lookup = None
    if not args.offline:
        client = KrdictClient(KRDICT_API_KEY, KrdictCache(KRDICT_CACHE_PATH))
        lookup = first_of(LocalDict(KRDICT_LOCAL_PATH).lookup, client.lookup_cached,
                          client.lookup if args.live else None)

    engine = make_engine()
    upgrade(engine)
    t0 = time.perf_counter()
    with make_sessionmaker(engine)() as session:
        for path in prepared_files(args.show, args.episodes or None):
            for doc in part_docs(args.show, load_prepared(path)):
                r = ingest_episode(session, doc, lookup, publish=args.publish)
                print(f"{r.episode_id}: coverage {r.coverage:.1%} over {r.content_tokens} content tokens, "
                      f"{len(r.new_lexemes)} new lexemes, {len(r.missing_gloss)} without gloss")
        d = derive(session)
        print(f"srs: {d.changed} state rows changed, {d.created} created")
        session.commit()
    print(f"done in {time.perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
