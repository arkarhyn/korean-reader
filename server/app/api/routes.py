"""Reader API under /api. Events are stored as-is; state is derived from the log by explicit jobs (placement fit; DECISIONS 8), except manual `set_state` overrides, applied on receipt (DECISIONS 54)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, selectinload

from ..db import get_session
from ..analyzer import proper_nouns
from ..coverage import known_by_alias
from ..events import apply_events
from ..ingest import raw_known_keys
from ..generation import build_context
from ..db.models import Episode, Event, Lexeme, LexemeState, utcnow
from ..placement import items as placement_items
from ..placement import service as placement
from .schemas import (EpisodeFull, EpisodeSummary, EventBatch, EventBatchResult, GrammarItemOut, LexemeOut,
                      LexemeStateOut, PlacementOut, QuestionOut, SyncPull, VocabItemOut)

router = APIRouter(prefix="/api")


def _summary(ep: Episode) -> EpisodeSummary:
    return EpisodeSummary.model_validate(ep, from_attributes=True)


def _lexeme_out(lx: Lexeme, raw_known: set[tuple[str, str]]) -> LexemeOut:
    out = LexemeOut.model_validate(lx, from_attributes=True)
    out.counts_known = ((lx.pos == "NNP" and lx.lemma in proper_nouns())
                        or known_by_alias(lx.lemma, lx.pos, raw_known))
    return out


def _full(session: Session, ep: Episode, raw_known: set[tuple[str, str]] | None = None) -> EpisodeFull:
    ids = {t["lex"] for p in ep.paragraphs for t in p.tokens if "lex" in t}
    lexemes = session.scalars(select(Lexeme).where(Lexeme.id.in_(ids))) if ids else []
    raw_known = raw_known_keys(session) if raw_known is None else raw_known
    return EpisodeFull(
        **_summary(ep).model_dump(),
        paragraphs=[{"idx": p.idx, "ko": p.ko, "en": p.en, "tokens": p.tokens} for p in ep.paragraphs],
        questions=[QuestionOut.model_validate(q, from_attributes=True) for q in ep.questions],
        lexemes={lx.id: _lexeme_out(lx, raw_known) for lx in lexemes},
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
    apply_events(session, session.scalars(select(Event).where(Event.id.in_(accepted))))
    session.commit()
    return EventBatchResult(accepted=accepted, duplicate=duplicate)


@router.get("/sync/pull", response_model=SyncPull)
def sync_pull(since: AwareDatetime | None = None, session: Session = Depends(get_session)):
    """Everything changed after `since` (all of it when omitted). Client stores server_time as its next cursor."""
    server_time = utcnow()
    raw_known = raw_known_keys(session)
    eps = _published().order_by(Episode.created_at)
    states = select(LexemeState)
    if since is not None:
        eps = eps.where(Episode.updated_at > since)
        states = states.where(LexemeState.updated_at > since)
    return SyncPull(
        server_time=server_time,
        episodes=[_full(session, ep, raw_known) for ep in session.scalars(eps)],
        lexeme_states=[LexemeStateOut.model_validate(s, from_attributes=True) for s in session.scalars(states)],
    )



@router.get("/export/generation-context")
def generation_context(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Input for a /generate-batch session (SPEC 5)."""
    return build_context(session)


@router.get("/placement", response_model=PlacementOut)
def get_placement(session: Session = Depends(get_session)):
    att = placement.latest_attempt(session)
    fitted = session.scalar(select(LexemeState.lexeme_id).where(LexemeState.source == "placement").limit(1))
    return PlacementOut(
        grammar=[GrammarItemOut(**{k: it[k] for k in ("id", "ko", "en")}) for it in placement_items.grammar_items()],
        vocab=[VocabItemOut(id=it["id"], word=it["word"]) for it in placement_items.vocab_items()],
        calibration=placement_items.calibration_ids(),
        completed_attempt=att.attempt_id if att else None,
        fitted=fitted is not None,
    )


@router.post("/placement/fit")
def fit_placement(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Fit the latest finished placement attempt from the event log and write states."""
    summary = placement.run(session)
    if summary is None:
        raise HTTPException(409, "no finished placement attempt has been synced")
    session.commit()
    return summary
