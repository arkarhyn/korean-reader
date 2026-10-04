"""Import the NIKL learner vocabulary list as lexemes with freq_rank / freq_band.

    uv run python scripts/import_nikl.py [--offline]

Needs data/nikl_vocab.txt (scripts/fetch_nikl_vocab.py). Glosses come from the
local krdict dump, then cached API responses. Re-runs only refresh rank/band
and fill missing glosses.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import KRDICT_API_KEY, KRDICT_CACHE_PATH, KRDICT_LOCAL_PATH, NIKL_VOCAB_PATH  # noqa: E402
from app.db import make_engine, make_sessionmaker  # noqa: E402
from app.db.migrate import upgrade  # noqa: E402
from app.ingest import first_of  # noqa: E402
from app.krdict.cache import KrdictCache  # noqa: E402
from app.krdict.client import KrdictClient  # noqa: E402
from app.krdict.local import LocalDict  # noqa: E402
from app.nikl import import_words, parse  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="no gloss lookups")
    args = ap.parse_args()

    words = parse(NIKL_VOCAB_PATH)
    print(f"{len(words)} (lemma, pos) entries: {dict(sorted(Counter(w.band for w in words).items()))}")
    lookup = None
    if not args.offline:
        client = KrdictClient(KRDICT_API_KEY, KrdictCache(KRDICT_CACHE_PATH))
        lookup = first_of(LocalDict(KRDICT_LOCAL_PATH).lookup, client.lookup_cached)

    engine = make_engine()
    upgrade(engine)
    with make_sessionmaker(engine)() as session:
        created, updated = import_words(session, words, lookup)
        session.commit()
    print(f"created {created}, updated {updated}")


if __name__ == "__main__":
    main()
