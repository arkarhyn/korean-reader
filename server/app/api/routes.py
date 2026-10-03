"""Reader API under /api. Events are stored as-is; no state is derived here (DECISIONS 8)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..db.models import Episode, Event, Lexeme, LexemeState, utcnow
from .schemas import (EpisodeFull, EpisodeSummary, EventBatch, EventBatchResult, LexemeOut, LexemeStateOut,
                      QuestionOut, SyncPull)

router = APIRouter(prefix="/api")


def _summary(ep: Episode) -> EpisodeSummary:
    return EpisodeSummary.model_validate(ep, from_attributes=True)


def _full(session: Session, ep: Episode) -> EpisodeFull:
    ids = {t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t}
    lexemes = session.scalars(select(Lexeme).where(Lexeme.id.in_(ids))) if ids else []
    return EpisodeFull(
        **_summary(ep).model_dump(),
        paragraphs=[{"idx": p.idx, "ko": p.ko, "en": p.en, "tokens": p.tokens} for p in ep.paragraphs],
        questions=[QuestionOut.model_validate(q, from_attributes=True) for q in ep.questions],
        lexemes={lx.id: LexemeOut.model_validate(lx, from_attributes=True) for lx in lexemes},
    )


def _published():
    return (select(Episode).where(Episode.status == "published")
            .options(selectinload(Episode.paragraphs), selectinload(Episode.questions)))


@router.get("/episodes", response_model=list[EpisodeSummary])
def list_episodes(session: Session = Depends(get_session)):
    eps = session.scalars(select(Episode).where(Episode.status == "published").order_by(Episode.created_at))
    return [_summary(ep) for ep in eps]


@router.get("/episodes/{episode_id}", response_model=EpisodeFull)
def get_episode(episode_id: str, session: Session = Depends(get_session)):
    ep = session.scalar(_published().where(Episode.id == episode_id))
    if ep is None:
        raise HTTPException(404, "episode not found")
    return _full(session, ep)


@router.post("/events/batch", response_model=EventBatchResult)
def post_events(batch: EventBatch, session: Session = Depends(get_session)):
    """Idempotent on event id: re-sent events are reported as duplicates and not changed."""
    accepted, duplicate = [], []
    now = utcnow()
    for ev in batch.events:
        ev_id = str(ev.id)
        stmt = insert(Event).values(id=ev_id, ts=ev.ts, device=ev.device, type=ev.type,
                                    payload=ev.payload, received_at=now).on_conflict_do_nothing()
        (accepted if session.execute(stmt).rowcount else duplicate).append(ev_id)
    session.commit()
    return EventBatchResult(accepted=accepted, duplicate=duplicate)


@router.get("/sync/pull", response_model=SyncPull)
def sync_pull(since: AwareDatetime | None = None, session: Session = Depends(get_session)):
    """Everything changed after `since` (all of it when omitted). Client stores server_time as its next cursor."""
    server_time = utcnow()
    eps = _published().order_by(Episode.created_at)
    states = select(LexemeState)
    if since is not None:
        eps = eps.where(Episode.updated_at > since)
        states = states.where(LexemeState.updated_at > since)
    return SyncPull(
        server_time=server_time,
        episodes=[_full(session, ep) for ep in session.scalars(eps)],
        lexeme_states=[LexemeStateOut.model_validate(s, from_attributes=True) for s in session.scalars(states)],
    )

