"""Re-derive SRS states (lexeme_state / grammar_state) from baseline + event log (app/srs.py).

    uv run python scripts/derive_srs.py [--db PATH] [--rebase] [--apply] [--check]

Default is a dry run: shows what a replay would change, then rolls back.
--rebase  rebuild the baseline columns first: placement fit (latest finished attempt)
          + flagged seed vocab. Needed once after migration 0003 on a DB with history.
--apply   commit the result.
--check   replay twice more and assert nothing changes (acceptance: replay is deterministic).
"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import make_engine, make_sessionmaker  # noqa: E402
from app.db.migrate import upgrade  # noqa: E402
from app.db.models import GrammarState, Lexeme, LexemeState  # noqa: E402
from app.generation import due_lexemes  # noqa: E402
from app.ingest import known_lexeme_ids  # noqa: E402
from app.placement import service as placement  # noqa: E402
from app.seed import load_flagged_vocab  # noqa: E402
from app.srs import derive  # noqa: E402


def rebase(session) -> None:
    """Baseline = what placement and the seed would write today (both deterministic)."""
    att = placement.latest_attempt(session)
    if att is not None:
        _, states = placement.fit(att, placement.gather(session, att))
        placement.apply_states(session, states)
        placement.apply_grammar(session, att)
    lexemes, grammar = load_flagged_vocab()
    for s in lexemes:
        row = session.scalar(select(LexemeState).join(Lexeme).where(Lexeme.lemma == s.lemma, Lexeme.pos == s.pos))
        if row is not None:
            row.base_state, row.base_source = s.state, s.source
    for g in grammar:
        if (row := session.get(GrammarState, g.code)) is not None:
            row.base_state, row.base_source = g.state, g.source
    session.flush()
    n = session.query(LexemeState).filter(LexemeState.base_state.is_not(None)).count()
    print(f"rebased: {n} lexeme baselines" + ("" if att else " (no placement attempt)"))


def summary(session) -> Counter:
    return Counter(session.scalars(select(LexemeState.state)))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, help="database path (default: DATABASE_PATH)")
    ap.add_argument("--rebase", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    engine = make_engine(args.db) if args.db else make_engine()
    upgrade(engine)
    with make_sessionmaker(engine)() as session:
        before = summary(session)
        known_before = known_lexeme_ids(session)
        if args.rebase:
            rebase(session)
        t = time.perf_counter()
        r = derive(session)
        ms = (time.perf_counter() - t) * 1000
        print(f"derive: {r.changed} rows changed, {r.created} created in {ms:.0f} ms")
        print(f"states before: {dict(before)}")
        print(f"states after:  {dict(summary(session))}")
        for (a, b), n in sorted(r.transitions.items(), key=lambda kv: -kv[1]):
            print(f"  {a:>8} -> {b:<8} {n}")

        lemma = dict(session.execute(select(Lexeme.id, Lexeme.lemma)).all())
        known_after = known_lexeme_ids(session)
        lost, gained = known_before - known_after, known_after - known_before
        print(f"counts known (SPEC 7): {len(known_before)} -> {len(known_after)}")
        if lost:
            print("  no longer known: " + ", ".join(sorted(lemma[i] for i in lost)))
        if gained:
            print("  newly known:     " + ", ".join(sorted(lemma[i] for i in gained)))
        due = due_lexemes(session)
        print(f"due now: {len(due)}; first 15: " + ", ".join(lx.lemma for lx, _ in due[:15]))

        if args.check:
            for _ in range(2):
                again = derive(session)
                assert again.changed == 0 and again.created == 0, f"replay not stable: {again}"
            print("check: replay is stable (2 more replays changed nothing)")
        if args.apply:
            session.commit()
            print("applied")
        else:
            session.rollback()
            print("dry run (rolled back); pass --apply to commit")


if __name__ == "__main__":
    main()
