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
| gloss_source | TEXT | `krdict` / `llm` / `manual` / `none` (no entry yet; retried on re-ingest) |
| freq_rank | INTEGER NULL | NIKL 학습용 어휘 목록 순위 (`scripts/import_nikl.py`) |
| freq_band | TEXT NULL | A / B / C (NIKL learner list) or numeric band |
| krdict_id | TEXT NULL | |
| UNIQUE(lemma, pos) | | never key by surface form |

### lexeme_state (one row per lexeme the user has any history with)
| column | type | notes |
|---|---|---|
| lexeme_id | FK PK | |
| state | TEXT | `new` / `seen` / `learning` / `known` / `ignored` |
| fsrs_card | JSON | py-fsrs 6 `Card.to_dict()` (card_id = lexeme id, stability, difficulty, due, last_review, state); derived |
| exposures | INTEGER | encounters without a tap (incl. non-due); derived |
| lookups | INTEGER | taps minus untaps; derived |
| first_seen_at | DATETIME | |
| last_seen_at | DATETIME | last completed encounter / set_state; derived |
| source | TEXT | `placement` / `episode` / `ingest` / `manual` |
| base_state | TEXT NULL | replay baseline written by placement / seed (migration 0003) |
| base_source | TEXT NULL | `placement` / `manual` (flagged seed) |
| updated_at | DATETIME | sync pull cursor (DECISIONS 35) |

`state`, `source`, `fsrs_card`, `exposures`, `lookups`, `last_seen_at` are rebuilt from
`base_state` + the event log by `app.srs.derive` (Stage 6). A `learning` word counts as
known until `last_review + stability` (retrievability 0.9) and is due after it.

### context_sentence (auto-built "card" fields)
| column | type | notes |
|---|---|---|
| id | PK | |
| lexeme_id | FK | |
| sentence_ko | TEXT | |
| sentence_en | TEXT NULL | |
| origin | TEXT | `episode:<id>` / `ingest:<id>` (indexed; replaced on re-ingest) |
| audio_ref | TEXT NULL | TTS cache key |
| start, end | INTEGER NULL | the word's span in `sentence_ko` (Quick review highlight; migration 0003) |

Filled by ingest, one row per (lexeme, sentence) of an episode; `sentence_en` is the
paragraph's translation.

## Grammar

### grammar_point
| column | type | notes |
|---|---|---|
| code | TEXT PK | e.g. `G.KIRO_HADA` |
| label_ko | TEXT | `-기로 하다` |
| ja_parallel | TEXT NULL | `〜ことにする` (filled from SYLLABUS_MAP) |
| ja_diff_note | TEXT NULL | where the parallel breaks |
| htsk_lesson | INTEGER NULL | syllabus position |
| kiwi_pattern | JSON | morpheme matcher: list of alternatives, each a list of `{form?, tag?, form_re?}` for consecutive Kiwi morphemes (`app/analyzer/patterns.py`). Filled for the Stage 5 targets and `new` points; rest in Stage 8 |
| prereqs | JSON | list of codes |

### grammar_state
Same shape as lexeme_state (incl. `updated_at`), keyed by grammar code. States:
`new` / `introduced` / `practicing` / `solid`.

## Content

### episode
| column | type | notes |
|---|---|---|
| id | TEXT PK | e.g. `S01E004` or `side-folk-002` |
| series | TEXT | `main` / `side-parent` / `side-folk` / `primer` / `legacy` / `placement` (calibration passages, hidden from the library) / `podcast` (Stage 7 parts, Listen tab only; not synced) |
| title_ko, title_en | TEXT | |
| register_tags | JSON | e.g. `["banmal","haeyo","hasipsio"]` |
| target_grammar | TEXT FK NULL | |
| new_lexemes | JSON | lexeme ids introduced |
| review_lexemes | JSON | due lexeme ids woven in |
| coverage | REAL | measured at generation |
| status | TEXT | `draft` / `published` / `retired` |
| source | TEXT NULL | e.g. `legacy:passage/20` |
| summary | TEXT NULL | one-line continuity note for the generator (migration 0002); podcast parts: the episode title |
| media | JSON NULL | podcast parts: `{kind: youtube, video_id, start_ms, end_ms, show, order, show_episode, episode_title, part, parts}` (migration 0004) |
| created_at | DATETIME | |
| updated_at | DATETIME | sync pull cursor |

### episode_paragraph
| episode_id, idx | PK | |
| ko | TEXT | |
| en | TEXT | |
| tokens | JSON | `[{s, e, lex}]` content / `[{s, e, g}]` coded grammar (DECISIONS 36) |
| meta | JSON NULL | podcast turns: `{speaker, uncertain?, start_ms, end_ms, lines: [{s, start_ms, end_ms, en}]}`, `s` = line offset in `ko` (migration 0004) |

### question
| id | PK | |
| episode_id | FK | |
| idx | INTEGER | order within episode |
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
| received_at | DATETIME | server time |

Types: `episode_open`, `word_tap`, `episode_complete`, `question_answer`,
`mine_word`, `flag_sentence`, `placement_answer`, `grammar_drill_answer`,
`set_state` (manual override, e.g. ignore), `word_untap` (Stage 5), `review_answer` (Stage 6),
`primer_request {episode_id}` (Stage 7: pre-teach a podcast part; fulfilled by a `primer` episode with `source = primer:<part id>`).

Payloads written by the Stage 3 reader:
`episode_open {episode_id}`, `word_tap {episode_id, paragraph_idx, start, end,
lexeme_id}`, `question_answer {episode_id, question_id, choice_idx, correct, ms}`,
`episode_complete {episode_id, tapped_lexeme_ids}`, `flag_sentence {episode_id,
paragraph_idx, start, end, text}`.

Stage 5 reader: `set_state {lexeme_id, state, prev_state?, episode_id?}` from the
popover: "I know this word" (state `known`), "I forgot this" (state `learning`);
the undo sends the previous state. Word-set checklists send the same
event with `word_set: <set id>` instead of `episode_id` (DECISIONS 68). The server
applies it on receipt (lexeme_state source `manual`, DECISIONS 54/56). `word_untap {episode_id,
paragraph_idx, start, end, lexeme_id}` cancels the latest `word_tap` of that
lexeme in the visit (mistap); `episode_complete.tapped_lexeme_ids` already
excludes it.

Stage 6 additions: `episode_complete.lexeme_ids` (every content lexeme in the version
read), `question_answer.kind` / `target_ref`, `set_state.undo: true` on an undo (the
replay restores the SRS card), and `review_answer {lexeme_id, context_id, choice_idx,
correct, ms}` from Quick review. Older events without the new fields fall back to the
current episode / question rows; question ids stay stable across re-ingest.

Placement (Stage 4) writes `placement_answer {attempt_id, section, ms, ...}`:
`grammar {item_id, got_it}`, `vocab {item_id, yes}`, `calibration {episode_id,
tapped_lexeme_ids, rating 1-5}` and `done {}`. Taps inside calibration passages
also log normal `word_tap` events. `POST /api/placement/fit` derives lexeme and
grammar states (source `placement`) from the latest attempt with a `done`
event; within an attempt the last answer per item wins.

Schema is managed by Alembic (`server/migrations/`).

FSRS updates are DERIVED from events, so scoring rules can change and state can be
rebuilt by replaying the log: `app.srs.derive` resets every state row to its baseline
and replays all events after each accepted event batch, after placement fit and after
ingest (`scripts/derive_srs.py` for dry runs and checks).

## Story continuity

### story_bible
Markdown in `docs/STORY_BIBLE.md` (human-edited) + `story_thread` table:
| id | PK | |
| summary | TEXT | one-line status of an open plot thread |
| opened_in | episode id | |
| closed_in | episode id NULL | |
