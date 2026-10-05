"""Quick review items (SPEC 3.2): due words with a stored context sentence and a 3-option meaning pick.

Built at sync pull from the derived due list; answers come back as `review_answer`
events and are graded in app/srs.py. No counts are exposed (no backlog UI).
"""

import random
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db.models import ContextSentence, Episode, Event, Lexeme
from .generation import due_lexemes

MAX_ITEMS = 20
DISTRACTOR_POOL = 60  # frequent glossed lexemes of the same POS


def _distractors(session: Session, lx: Lexeme) -> list[str]:
    pool = session.scalars(select(Lexeme.gloss_en)
                           .where(Lexeme.pos == lx.pos, Lexeme.id != lx.id, Lexeme.gloss_en != "",
                                  Lexeme.gloss_source.in_(("krdict", "manual")), Lexeme.freq_rank.is_not(None))
                           .order_by(Lexeme.freq_rank).limit(DISTRACTOR_POOL)).all()
    pool = sorted({g for g in pool if g.lower() != lx.gloss_en.lower()})
    return random.Random(lx.id).sample(pool, 2) if len(pool) >= 2 else []


def review_items(session: Session) -> list[dict[str, Any]]:
    published = dict(session.execute(select(Episode.id, Episode.series).where(Episode.status == "published")).all())
    read = {ev.payload.get("episode_id") for ev in session.scalars(select(Event).where(Event.type == "episode_complete"))}
    items = []
    for lx, _ in due_lexemes(session):
        if len(items) >= MAX_ITEMS:
            break
        if not lx.gloss_en:
            continue
        contexts = [c for c in session.scalars(select(ContextSentence).where(ContextSentence.lexeme_id == lx.id))
                    if c.start is not None and published.get(c.origin.removeprefix("episode:"), "placement") != "placement"]
        if not contexts:
            continue
        ctx = max(contexts, key=lambda c: (c.origin.removeprefix("episode:") in read, c.id))
        wrong = _distractors(session, lx)
        if len(wrong) < 2:
            continue
        options = [lx.gloss_en, *wrong]
        random.Random(lx.id * 7919).shuffle(options)
        items.append({
            "lexeme_id": lx.id, "lemma": lx.lemma, "pos": lx.pos, "gloss_en": lx.gloss_en, "hanja": lx.hanja,
            "context_id": ctx.id, "sentence_ko": ctx.sentence_ko, "sentence_en": ctx.sentence_en,
            "start": ctx.start, "end": ctx.end, "options": options, "answer_idx": options.index(lx.gloss_en),
        })
    return items
