"""Event effects applied on receipt. Only `set_state` changes state immediately
(a manual override, DECISIONS 54); everything else waits for derivation jobs
(DECISIONS 8). Applying is idempotent, so the log can be replayed.
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import Event, Lexeme, LexemeState

LEXEME_STATES = ("new", "seen", "learning", "known", "ignored")


def apply_set_state(session: Session, ev: Event) -> bool:
    """`set_state {lexeme_id, state}` -> lexeme_state row with source `manual`. False if the payload is unusable."""
    p = ev.payload
    lex_id, state = p.get("lexeme_id"), p.get("state")
    if state not in LEXEME_STATES or not isinstance(lex_id, int) or session.get(Lexeme, lex_id) is None:
        return False
    st = session.get(LexemeState, lex_id)
    if st is None:
        st = LexemeState(lexeme_id=lex_id, state=state, source="manual", first_seen_at=ev.ts)
        session.add(st)
    st.state, st.source = state, "manual"
    st.last_seen_at = max(filter(None, (st.last_seen_at, ev.ts)))
    return True


def apply_events(session: Session, events: Iterable[Event]) -> None:
    for ev in sorted(events, key=lambda e: e.ts):
        if ev.type == "set_state":
            apply_set_state(session, ev)
    session.flush()


def replay_manual_states(session: Session) -> None:
    """Re-apply every set_state in client-time order (later overrides win)."""
    apply_events(session, session.scalars(select(Event).where(Event.type == "set_state")))
