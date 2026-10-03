"""Authoring format for episode JSON in content/episodes/ (input to ingest).

Mirrors DATA_MODEL `episode`, `episode_paragraph`, `question`. Tokens and
coverage are computed at ingest, not authored.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Series = Literal["main", "side-parent", "side-folk", "primer", "legacy"]
Register = Literal["banmal", "haeyo", "hasipsio"]


class Paragraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ko: str = Field(min_length=1)
    en: str = Field(min_length=1)


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["comprehension", "meaning_check", "grammar_check"]
    prompt_ko: str
    prompt_en: str
    options: list[str] = Field(min_length=3, max_length=4)
    answer_idx: int
    target_ref: str | None = None

    @model_validator(mode="after")
    def _answer_in_range(self):
        if not 0 <= self.answer_idx < len(self.options):
            raise ValueError("answer_idx out of range")
        return self


class Episode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    series: Series
    title_ko: str
    title_en: str
    register_tags: list[Register]
    target_grammar: str | None = None
    status: Literal["draft", "published", "retired"] = "draft"
    source: str | None = None
    paragraphs: list[Paragraph] = Field(min_length=1)
    questions: list[Question] = []

    @property
    def text_ko(self) -> str:
        return "\n".join(p.ko for p in self.paragraphs)


def load_episode(path: Path) -> Episode:
    return Episode.model_validate(json.loads(path.read_text(encoding="utf-8")))
