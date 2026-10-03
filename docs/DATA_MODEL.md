# DATA_MODEL -- korean-reader v1

SQLite on the home server is the source of truth. Clients hold a cached
subset in IndexedDB (Dexie) and an outbound event queue.

## Lexicon

### lexeme
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| lemma | TEXT | dictionary form, e.g. `만나다` |
| pos | TEXT | Kiwi POS tag family (NNG, NNP, VV, VA, MAG, ...) |
| hanja | TEXT NULL | e.g. `時間` for 시간 |
| gloss_en | TEXT | |
| gloss_ja | TEXT NULL | |
| gloss_source | TEXT | `krdict` / `llm` / `manual` |
| freq_rank | INTEGER NULL | from learner/frequency list |
| freq_band | TEXT NULL | A / B / C (NIKL learner list) or numeric band |
| krdict_id | TEXT NULL | |
| UNIQUE(lemma, pos) | | never key by surface form |

### lexeme_state (one row per lexeme the user has any history with)
| column | type | notes |
|---|---|---|
| lexeme_id | FK PK | |
| state | TEXT | `new` / `seen` / `learning` / `known` / `ignored` |
| fsrs_card | JSON | py-fsrs card (stability, difficulty, due, reps, lapses, state) |
| exposures | INTEGER | encounters without a tap (incl. non-due) |
| lookups | INTEGER | taps |
| first_seen_at | DATETIME | |
| last_seen_at | DATETIME | |
| source | TEXT | `placement` / `episode` / `ingest` / `manual` |

### context_sentence (auto-built "card" fields)
| column | type | notes |
|---|---|---|
| id | PK | |
| lexeme_id | FK | |
| sentence_ko | TEXT | |
| sentence_en | TEXT NULL | |
| origin | TEXT | `episode:<id>` / `ingest:<id>` |
| audio_ref | TEXT NULL | TTS cache key |

## Grammar

### grammar_point
| column | type | notes |
|---|---|---|
| code | TEXT PK | e.g. `G.KIRO_HADA` |
| label_ko | TEXT | `-기로 하다` |
| ja_parallel | TEXT | `〜ことにする` |
| ja_diff_note | TEXT NULL | where the parallel breaks |
| htsk_lesson | INTEGER NULL | syllabus position |
| kiwi_pattern | JSON | morpheme sequence matcher |
| prereqs | JSON | list of codes |

### grammar_state
Same shape as lexeme_state, keyed by grammar code. States:
`new` / `introduced` / `practicing` / `solid`.

## Content

### episode
| column | type | notes |
|---|---|---|
| id | TEXT PK | e.g. `S01E004` or `side-folk-002` |
| series | TEXT | `main` / `side-parent` / `side-folk` / `primer` |
| title_ko, title_en | TEXT | |
| register_tags | JSON | e.g. `["banmal","haeyo","hasipsio"]` |
| target_grammar | TEXT FK NULL | |
| new_lexemes | JSON | lexeme ids introduced |
| review_lexemes | JSON | due lexeme ids woven in |
| coverage | REAL | measured at generation |
| status | TEXT | `draft` / `published` / `retired` |
| created_at | DATETIME | |

### episode_paragraph
| episode_id, idx | PK | |
| ko | TEXT | |
| en | TEXT | |
| tokens | JSON | Kiwi analysis: surface span -> lexeme_id / grammar code |

### question
| id | PK | |
| episode_id | FK | |
| kind | TEXT | `comprehension` / `meaning_check` / `grammar_check` |
| prompt_ko, prompt_en | TEXT | |
| options | JSON | 3-4 choices |
| answer_idx | INTEGER | |
| target_ref | TEXT NULL | lexeme id or grammar code being checked |

### ingest_doc
| id | PK | |
| title | TEXT | |
| raw_text | TEXT | private, never exported |
| coverage | REAL | |
| analyzed_at | DATETIME | |

## Events (append-only; drives everything)

### event
| column | type | notes |
|---|---|---|
| id | TEXT PK | UUID v4 generated on client -> idempotent sync |
| ts | DATETIME | client time |
| device | TEXT | `laptop` / `iphone` |
| type | TEXT | see below |
| payload | JSON | |

Types: `episode_open`, `word_tap`, `episode_complete`, `question_answer`,
`mine_word`, `flag_sentence`, `placement_answer`, `grammar_drill_answer`,
`set_state` (manual override, e.g. ignore).

FSRS updates are DERIVED from events in a server job, so scoring rules can
change and state can be rebuilt by replaying the log.

## Story continuity

### story_bible
Markdown in `docs/STORY_BIBLE.md` (human-edited) + `story_thread` table:
| id | PK | |
| summary | TEXT | one-line status of an open plot thread |
| opened_in | episode id | |
| closed_in | episode id NULL | |
