"""SQLite schema (docs/DATA_MODEL.md). Migrations live in server/migrations/."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class UtcDateTime(TypeDecorator):
    """Stored as naive UTC (SQLite has no tz); always returned tz-aware."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime; use timezone-aware values")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return value.replace(tzinfo=UTC) if value is not None else None


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UtcDateTime, dict[str, Any]: JSON, list[Any]: JSON}


# ---- Lexicon ----

class Lexeme(Base):
    __tablename__ = "lexeme"
    __table_args__ = (UniqueConstraint("lemma", "pos"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lemma: Mapped[str] = mapped_column(String)
    pos: Mapped[str] = mapped_column(String)
    hanja: Mapped[str | None]
    gloss_en: Mapped[str] = mapped_column(Text, default="")
    gloss_ja: Mapped[str | None] = mapped_column(Text)
    gloss_source: Mapped[str] = mapped_column(String)  # krdict / llm / manual / none
    freq_rank: Mapped[int | None]
    freq_band: Mapped[str | None]
    krdict_id: Mapped[str | None]

    state: Mapped["LexemeState | None"] = relationship(back_populates="lexeme")


class LexemeState(Base):
    __tablename__ = "lexeme_state"

    lexeme_id: Mapped[int] = mapped_column(ForeignKey("lexeme.id"), primary_key=True)
    state: Mapped[str] = mapped_column(String)  # new / seen / learning / known / ignored
    fsrs_card: Mapped[dict[str, Any] | None]
    exposures: Mapped[int] = mapped_column(Integer, default=0)
    lookups: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime | None]
    last_seen_at: Mapped[datetime | None]
    source: Mapped[str] = mapped_column(String)  # placement / episode / ingest / manual
    # Replay baseline written by placement / seed; app/srs.py derives the rest from events.
    base_state: Mapped[str | None]
    base_source: Mapped[str | None]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)

    lexeme: Mapped[Lexeme] = relationship(back_populates="state")


class ContextSentence(Base):
    __tablename__ = "context_sentence"

    id: Mapped[int] = mapped_column(primary_key=True)
    lexeme_id: Mapped[int] = mapped_column(ForeignKey("lexeme.id"), index=True)
    sentence_ko: Mapped[str] = mapped_column(Text)
    sentence_en: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String, index=True)  # episode:<id> / ingest:<id>
    audio_ref: Mapped[str | None]
    start: Mapped[int | None]  # the word's span inside sentence_ko
    end: Mapped[int | None]


# ---- Grammar ----

class GrammarPoint(Base):
    __tablename__ = "grammar_point"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    label_ko: Mapped[str] = mapped_column(String)
    ja_parallel: Mapped[str | None]  # filled from SYLLABUS_MAP (Stage 8)
    ja_diff_note: Mapped[str | None] = mapped_column(Text)
    htsk_lesson: Mapped[int | None]
    kiwi_pattern: Mapped[list[Any] | None]
    prereqs: Mapped[list[Any]] = mapped_column(default=list)
    teach_order: Mapped[float | None]  # overrides htsk_lesson for teaching order (Stage 8)
    lesson: Mapped[dict[str, Any] | None]  # lesson card, content/grammar/lessons/<code>.json

    @property
    def order(self) -> float:
        """Position in the teaching order: teach_order, else the HTSK lesson (unplaced last)."""
        if self.teach_order is not None:
            return self.teach_order
        return float(self.htsk_lesson) if self.htsk_lesson is not None else 999.0


class GrammarState(Base):
    __tablename__ = "grammar_state"

    code: Mapped[str] = mapped_column(ForeignKey("grammar_point.code"), primary_key=True)
    state: Mapped[str] = mapped_column(String)  # new / introduced / practicing / solid
    fsrs_card: Mapped[dict[str, Any] | None]
    exposures: Mapped[int] = mapped_column(Integer, default=0)
    lookups: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime | None]
    last_seen_at: Mapped[datetime | None]
    source: Mapped[str] = mapped_column(String)
    base_state: Mapped[str | None]
    base_source: Mapped[str | None]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


# ---- Content ----

class Episode(Base):
    __tablename__ = "episode"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    series: Mapped[str] = mapped_column(String)
    title_ko: Mapped[str]
    title_en: Mapped[str]
    register_tags: Mapped[list[Any]] = mapped_column(default=list)
    target_grammar: Mapped[str | None] = mapped_column(ForeignKey("grammar_point.code"))
    new_lexemes: Mapped[list[Any]] = mapped_column(default=list)
    review_lexemes: Mapped[list[Any]] = mapped_column(default=list)
    coverage: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, index=True)  # draft / published / retired
    source: Mapped[str | None]
    summary: Mapped[str | None] = mapped_column(Text)  # one-line continuity note for the generator
    media: Mapped[dict[str, Any] | None]  # podcast parts: YouTube id + time range (migration 0004)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)

    paragraphs: Mapped[list["EpisodeParagraph"]] = relationship(
        order_by="EpisodeParagraph.idx", cascade="all, delete-orphan")
    questions: Mapped[list["Question"]] = relationship(order_by="Question.idx", cascade="all, delete-orphan")


class EpisodeParagraph(Base):
    __tablename__ = "episode_paragraph"

    episode_id: Mapped[str] = mapped_column(ForeignKey("episode.id"), primary_key=True)
    idx: Mapped[int] = mapped_column(primary_key=True)
    ko: Mapped[str] = mapped_column(Text)
    en: Mapped[str] = mapped_column(Text)
    # [{"s", "e", "lex": lexeme_id}] for content, [{"s", "e", "g": code}] for coded grammar
    tokens: Mapped[list[Any]] = mapped_column(default=list)
    meta: Mapped[dict[str, Any] | None]  # podcast turns: speaker + timed subtitle lines (migration 0004)


class Question(Base):
    __tablename__ = "question"

    id: Mapped[int] = mapped_column(primary_key=True)
    episode_id: Mapped[str] = mapped_column(ForeignKey("episode.id"), index=True)
    idx: Mapped[int]
    kind: Mapped[str] = mapped_column(String)  # comprehension / meaning_check / grammar_check
    prompt_ko: Mapped[str] = mapped_column(Text)
    prompt_en: Mapped[str] = mapped_column(Text)
    options: Mapped[list[Any]]
    answer_idx: Mapped[int]
    target_ref: Mapped[str | None]


class IngestDoc(Base):
    __tablename__ = "ingest_doc"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    raw_text: Mapped[str] = mapped_column(Text)  # private, never exported
    coverage: Mapped[float | None] = mapped_column(Float)
    analyzed_at: Mapped[datetime | None]


# ---- Events (append-only) ----

class Event(Base):
    __tablename__ = "event"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # client UUID v4
    ts: Mapped[datetime] = mapped_column(index=True)  # client time
    device: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict[str, Any]]
    received_at: Mapped[datetime] = mapped_column(default=utcnow)


# ---- Story continuity ----

class StoryThread(Base):
    __tablename__ = "story_thread"

    id: Mapped[int] = mapped_column(primary_key=True)
    summary: Mapped[str] = mapped_column(Text)
    opened_in: Mapped[str] = mapped_column(ForeignKey("episode.id"))
    closed_in: Mapped[str | None] = mapped_column(ForeignKey("episode.id"))
