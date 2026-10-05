"""Reader API under /api. Events are stored as-is; every accepted batch re-derives all states from the log (app/srs.py; DECISIONS 8)."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session, selectinload

from .. import word_sets
from ..analyzer import proper_nouns
from ..coverage import known_by_alias
from ..db import get_session
from ..db.models import Episode, Event, GrammarPoint, GrammarState, Lexeme, LexemeState, utcnow
from ..generation import build_context
from ..ingest import raw_known_keys
from ..placement import items as placement_items
from ..placement import service as placement
from ..podcasts import podcasts_out
from ..review import review_items
from ..srs import derive, known_until, load_card
from .schemas import (CompletedOut, EpisodeFull, EpisodeSummary, EventBatch, EventBatchResult, GrammarItemOut, GrammarPointOut, LexemeOut,
                      LexemeStateOut, PlacementOut, QuestionOut, ReviewItemOut, SyncPull, VocabItemOut)

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
        paragraphs=[{"idx": p.idx, "ko": p.ko, "en": p.en, "tokens": p.tokens, "meta": p.meta}
                    for p in ep.paragraphs],
        questions=[QuestionOut.model_validate(q, from_attributes=True) for q in ep.questions],
        lexemes={lx.id: _lexeme_out(lx, raw_known) for lx in lexemes},
    )


def _published():
    return (select(Episode).where(Episode.status == "published")
            .options(selectinload(Episode.paragraphs), selectinload(Episode.questions)))


@router.get("/episodes", response_model=list[EpisodeSummary])
def list_episodes(session: Session = Depends(get_session)):
    eps = session.scalars(select(Episode).where(Episode.status == "published", Episode.series != "podcast")
                          .order_by(Episode.created_at))
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
    if accepted:
        derive(session)
    session.commit()
    return EventBatchResult(accepted=accepted, duplicate=duplicate)


@router.get("/sync/pull", response_model=SyncPull)
def sync_pull(since: AwareDatetime | None = None, session: Session = Depends(get_session)):
    """Everything changed after `since` (all of it when omitted). Client stores server_time as its next cursor."""
    server_time = utcnow()
    raw_known = raw_known_keys(session)
    # Podcast parts are long and only read online: fetched one by one (GET /episodes/{id}), not synced.
    eps = _published().where(Episode.series != "podcast").order_by(Episode.created_at)
    states = select(LexemeState)
    # Read marks always go out in full: one row per finished episode, and devices that
    # synced before this existed would otherwise never get the earlier ones.
    done = select(Event).where(Event.type == "episode_complete").order_by(Event.ts)
    if since is not None:
        eps = eps.where(Episode.updated_at > since)
        states = states.where(LexemeState.updated_at > since)
    completed: dict[str, CompletedOut] = {}
    for ev in session.scalars(done):
        if (ep_id := ev.payload.get("episode_id")) and ep_id not in completed:
            completed[ep_id] = CompletedOut(episode_id=ep_id, completed_at=ev.ts)
    return SyncPull(
        server_time=server_time,
        episodes=[_full(session, ep, raw_known) for ep in session.scalars(eps)],
        lexeme_states=[_state_out(s) for s in session.scalars(states)],
        completed=list(completed.values()),
        review_items=[ReviewItemOut(**it) for it in review_items(session)],
        grammar=grammar_out(session),
    )


def grammar_out(session: Session) -> list[GrammarPointOut]:
    """Every grammar point in teaching order with its state and lesson card (the client gates on these)."""
    states = {g.code: g.state for g in session.scalars(select(GrammarState))}
    points = sorted(session.scalars(select(GrammarPoint)), key=lambda gp: (gp.order, gp.code))
    return [GrammarPointOut(code=gp.code, label_ko=gp.label_ko, htsk_lesson=gp.htsk_lesson, teach_order=gp.order,
                            state=states.get(gp.code, "new"), ja_parallel=gp.ja_parallel,
                            ja_diff_note=gp.ja_diff_note, lesson=gp.lesson) for gp in points]


def _state_out(s: LexemeState) -> LexemeStateOut:
    return LexemeStateOut(lexeme_id=s.lexeme_id, state=s.state, updated_at=s.updated_at,
                          due=known_until(load_card(s.fsrs_card)))



@router.get("/podcasts")
def list_podcasts(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Shows -> episodes -> parts for the Listen tab (Stage 7). Read marks come from sync `completed`."""
    return podcasts_out(session)


@router.get("/export/generation-context")
def generation_context(session: Session = Depends(get_session)) -> dict[str, Any]:
    """Input for a /generate-batch session (SPEC 5)."""
    return build_context(session)


@router.get("/word-sets")
def get_word_sets(session: Session = Depends(get_session)) -> list[dict[str, Any]]:
    """Themed word sets with each item's lexeme ids and known flag (DECISIONS 67)."""
    return word_sets.sets_out(session)


@router.get("/word-sets/common")
def get_common_words(offset: int = Query(0, ge=0), limit: int = Query(40, ge=1, le=100),
                     session: Session = Depends(get_session)) -> dict[str, Any]:
    """The frequency walk: NIKL-ranked words not yet known, one page at a time."""
    return word_sets.common_out(session, offset, limit)


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
