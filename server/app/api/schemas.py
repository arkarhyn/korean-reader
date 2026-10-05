from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

EventType = Literal[
    "episode_open", "word_tap", "episode_complete", "question_answer", "mine_word",
    "flag_sentence", "placement_answer", "grammar_drill_answer", "set_state", "word_untap", "review_answer",
    "primer_request", "grammar_lesson_complete",
]


class EpisodeSummary(BaseModel):
    id: str
    series: str
    title_ko: str
    title_en: str
    register_tags: list[str]
    target_grammar: str | None
    coverage: float | None
    updated_at: datetime
    media: dict[str, Any] | None = None  # podcast parts: YouTube id + time range


class ParagraphOut(BaseModel):
    idx: int
    ko: str
    en: str
    tokens: list[dict[str, Any]]
    meta: dict[str, Any] | None = None  # podcast turns: speaker + timed lines


class QuestionOut(BaseModel):
    id: int
    kind: str
    prompt_ko: str
    prompt_en: str
    options: list[str]
    answer_idx: int
    target_ref: str | None


class LexemeOut(BaseModel):
    lemma: str
    pos: str
    gloss_en: str
    gloss_ja: str | None
    hanja: str | None
    # Counts as known whatever its own state says: a story-bible name, or known
    # under another tag of the same word (coverage.known_aliases).
    counts_known: bool = False


class EpisodeFull(EpisodeSummary):
    paragraphs: list[ParagraphOut]
    questions: list[QuestionOut]
    lexemes: dict[int, LexemeOut]


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    ts: AwareDatetime
    device: Literal["laptop", "iphone"]
    type: EventType
    payload: dict[str, Any] = {}


class EventBatch(BaseModel):
    events: list[EventIn] = Field(max_length=1000)


class EventBatchResult(BaseModel):
    accepted: list[str]
    duplicate: list[str]


class LexemeStateOut(BaseModel):
    lexeme_id: int
    state: str
    updated_at: datetime
    # When a reviewed card's retrievability falls to 0.9 (last review + stability): a `learning`
    # word counts as known until then (SPEC 7) and is due after it.
    due: datetime | None = None


class CompletedOut(BaseModel):
    episode_id: str
    completed_at: datetime  # client time of the first episode_complete


class ReviewItemOut(BaseModel):
    lexeme_id: int
    lemma: str
    pos: str
    gloss_en: str
    hanja: str | None
    context_id: int
    sentence_ko: str
    sentence_en: str | None
    start: int  # the word's span in sentence_ko
    end: int
    options: list[str]  # 3 English glosses
    answer_idx: int


class GrammarPointOut(BaseModel):
    code: str
    label_ko: str
    htsk_lesson: int | None
    teach_order: float  # GrammarPoint.order: teach_order, else the HTSK lesson
    state: str  # new / introduced / practicing / solid (no row = new)
    ja_parallel: str | None
    ja_diff_note: str | None
    lesson: dict[str, Any] | None  # lesson card (Stage 8), NULL until written


class SyncPull(BaseModel):
    server_time: datetime
    episodes: list[EpisodeFull]
    lexeme_states: list[LexemeStateOut]
    completed: list[CompletedOut] = []  # read marks from every device; always the full list
    review_items: list[ReviewItemOut] = []  # Quick review: due words, always the full (short) list
    grammar: list[GrammarPointOut] = []  # every grammar point + state + lesson card, always the full list


class GrammarItemOut(BaseModel):
    id: str
    ko: str
    en: str


class VocabItemOut(BaseModel):
    id: str
    word: str  # real/pseudo is not sent to the client


class PlacementOut(BaseModel):
    grammar: list[GrammarItemOut]
    vocab: list[VocabItemOut]
    calibration: list[str]  # episode ids (series "placement", delivered by sync pull)
    completed_attempt: str | None  # latest attempt with a `done` event
    fitted: bool  # placement states exist
