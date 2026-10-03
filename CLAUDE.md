# CLAUDE.md -- korean-reader

Private, single-user Korean learning app. Generates graded readers (serialized
family slice-of-life fiction) at 95-98% known-word coverage, tracks vocabulary
and grammar by dictionary form, and runs a hidden SRS driven by reading signals.

## Read first, every session
1. `docs/ROADMAP.md` -- current stage and its acceptance criteria
2. `docs/STATUS.md`  -- what the last session finished and left open
3. `docs/DECISIONS.md` -- do NOT reverse a logged decision without asking

Reference as needed: `docs/SPEC.md`, `docs/DATA_MODEL.md`,
`docs/LEARNER_PROFILE.md` (all content generation),
`docs/STORY_BIBLE.md` (Stage 5+), `docs/SYLLABUS_MAP.md` (Stage 8).

## Working rules
- One roadmap stage per session. Use plan mode before editing files.
- Stop and ask at any fork not covered by the docs.
- End every session by updating `docs/STATUS.md` (done / next / open issues)
  and appending to `docs/DECISIONS.md` for any new decision
  (date, decision, rejected alternative, reason).
- No paid APIs. No Anthropic API calls from the app. Content generation
  happens inside Claude Code sessions (see SPEC "Generation").
- No Ollama in v1.
- No visible flashcards, no streaks.
- Mobile UI: select / tap only. No required typing on phone views.

## Stack
- `server/`: Python 3.12, FastAPI, SQLite (via SQLAlchemy 2.x),
  kiwipiepy (morphological analysis), py-fsrs (scheduling)
- `web/`: React + TypeScript + Vite, vite-plugin-pwa, Tailwind,
  Dexie (IndexedDB) for offline client store
- `content/`: generated episode JSON (input to the ingest pipeline)
- `legacy/Graded-Reader-Project/`: previous app (FastAPI + Kiwi + Gemini),
  design reference only. Its `.env` and `data/vocab.db` are gitignored.

## Commands (fill in as they exist)
- server setup: `cd server; uv sync` (Python 3.12 pinned via `.python-version`)
- server dev: `cd server; uv run uvicorn app.main:app --reload`
- web dev: `TBD` (Stage 3)
- tests: `cd server; uv run pytest` (live krdict test runs only if `KRDICT_API_KEY` is set)
- export legacy vocab: `cd server; uv run python scripts/export_legacy_vocab.py`
- record krdict fixtures: `cd server; uv run python scripts/record_krdict_fixtures.py [words...]`
- coverage check: `TBD` (Stage 5)

## Conventions
- Lexemes keyed by (lemma, pos). Never key vocabulary by surface form.
- Grammar points keyed by stable code (e.g. `G.KIRO_HADA`), mapped to
  Kiwi morpheme patterns.
- Events are append-only, UUID-keyed, idempotent on sync.
