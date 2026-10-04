"""Fit the latest finished placement attempt and print the summary (Stage 4 acceptance).

    uv run python scripts/placement_report.py [--apply]

Without --apply nothing is written (the fit runs inside a rolled-back transaction).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import make_engine, make_sessionmaker  # noqa: E402
from app.db.migrate import upgrade  # noqa: E402
from app.placement.service import run  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write states (same as POST /api/placement/fit)")
    args = ap.parse_args()

    engine = make_engine()
    upgrade(engine)
    with make_sessionmaker(engine)() as session:
        s = run(session)
        if s is None:
            sys.exit("no finished placement attempt in the event log")
        session.commit() if args.apply else session.rollback()

    p = s["params"]
    print(f"attempt {s['attempt_id']}: {s['minutes']} min ({s['started_at']} -> {s['finished_at']})")
    print(f"model: a={p['a']:.2f} b={p['b']:.2f}  false alarms {s['pseudo']['yes']}/{s['pseudo']['total']}"
          f" (fa={p['fa']:.3f})  P(known)=threshold at rank {s['vocab_edge_rank']:,.0f}")
    print(f"lexeme states: {s['known_lexemes']} known, {s['seen_lexemes']} seen")
    for b in s["bands"]:
        print(f"  rank band {b['quantile']}: yes {b['yes']:.0%}  corrected {b['corrected']:.0%}  (n={b['n']})")
    for st, codes in s["grammar"].items():
        print(f"grammar {st}: {len(codes)}" + (f"  {' '.join(codes)}" if st != "solid" else ""))
    print("calibration (leave-one-out):")
    for r in s["calibration"]:
        print(f"  {r['episode_id']}: observed {r['observed']:.1%}  predicted {r['predicted']:.1%}"
              f"  expected {r['expected']:.1%}  95% [{r['interval'][0]:.1%}, {r['interval'][1]:.1%}]"
              f"  over {r['tokens']} tokens  rating {r['rating']}"
              f"  {'OK' if r['ok'] else 'MISS'}")
    print(f"pooled expected - observed: {s['pooled_error']:+.1%}")
    print(f"time <= 25 min: {'OK' if s['minutes'] <= 25 else 'MISS'};  calibration: "
          f"{'OK' if s['accepted'] else 'MISS'}{'' if args.apply else '  (dry run; --apply to write)'}")


if __name__ == "__main__":
    main()
