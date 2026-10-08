"""Check episode drafts against the generation targets (SPEC 5 step 3).

    uv run python scripts/coverage_check.py DRAFT.json [...] [--json]

Per draft: coverage (95-98%), new words (5-8), due words woven in, target grammar
count (4-6), length (500-900 hangul), and grammar used at state `new`. Unknown
words are listed so they can be swapped. Exit code 1 if any draft fails.
"""
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.content.schema import load_episode  # noqa: E402
from app.db import make_engine, make_sessionmaker  # noqa: E402
from app.generation import batch_due_coverage, check_draft  # noqa: E402
from app.ingest import known_keys  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    with make_sessionmaker(make_engine())() as session:
        known = known_keys(session)
        docs = [load_episode(p) for p in args.paths]
        reports = [check_draft(session, d, known) for d in docs]
        covered, missing = batch_due_coverage(session, docs)
    if args.json:
        print(json.dumps([asdict(r) | {"ok": r.ok} for r in reports], ensure_ascii=False, indent=1))
    else:
        for r in reports:
            print(f"{r.episode_id}: {'OK' if r.ok else 'FAIL'}  coverage {r.coverage:.1%} of {r.content_tokens} "
                  f"tokens, {r.hangul} hangul, {r.target_grammar} x{r.target_count}, "
                  f"{len(r.new_words)} new, {len(r.due_words)} due")
            for p in r.problems:
                print(f"  ! {p}")
            for w in r.warnings:
                print(f"  ~ {w}")
            for u in r.unknown:
                tag = f"due:{u.state}" if u.is_due else (u.state or "no row")
                rank = f"#{u.rank}" if u.rank else "unranked"
                print(f"    {u.lemma}/{u.pos} x{u.count}  [{tag}, {rank}]  {u.gloss}")
        if len(docs) > 1 or missing:
            n = len(covered) + len(missing)
            print(f"batch: due top-{n} covered {len(covered)}/{n}"
                  + (f"; not yet used: {', '.join(missing)}" if missing else ""))
    sys.exit(0 if all(r.ok for r in reports) else 1)


if __name__ == "__main__":
    main()
