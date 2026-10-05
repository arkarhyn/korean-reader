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
- server dev: `cd server; uv run uvicorn app.main:app --reload` (needs `uv run alembic upgrade head` first)
- web setup: `cd web; npm install` (Node at `C:\Program Files\nodejs`)
- web dev: `cd web; npm run dev` (proxies `/api` to the server on :8000:
  `cd server; $env:SERVER_PORT=8000; uv run python scripts/serve.py`)
- web build: `cd web; npm run build` (FastAPI serves `web/dist` at `/`)
- web tests: `cd web; npm test`
- ingest episodes: `cd server; uv run python scripts/ingest_episodes.py [paths] --publish [--seed] [--live | --offline]`
- serve (migrates first; TLS if cert env set): `cd server; uv run python scripts/serve.py`
- new migration: `cd server; uv run alembic revision --autogenerate -m <msg>`
- install / update Windows service (elevated): `powershell -ExecutionPolicy Bypass -File server\scripts\install_service.ps1`
- tests: `cd server; uv run pytest` (live krdict test runs only if `KRDICT_API_KEY` is set)
- export legacy vocab: `cd server; uv run python scripts/export_legacy_vocab.py`
- build local krdict dictionary (once, ~390 MB download): `cd server; uv run python scripts/build_krdict_local.py`
- record krdict fixtures: `cd server; uv run python scripts/record_krdict_fixtures.py [words...]`
- NIKL learner vocab (once): `cd server; uv run python scripts/fetch_nikl_vocab.py; uv run python scripts/import_nikl.py`
- rebuild placement vocab test: `cd server; uv run python scripts/build_placement.py`
- ingest calibration passages: `cd server; uv run python scripts/ingest_episodes.py --seed --publish ../content/placement/calibration/*.json`
- placement report (dry run; `--apply` writes): `cd server; uv run python scripts/placement_report.py`
- generation context: `cd server; uv run python scripts/export_context.py` (-> `content/generation-context.json`; also `GET /api/export/generation-context`)
- coverage check: `cd server; uv run python scripts/coverage_check.py ../content/episodes/s01/S01E001.json ...` (exit 1 on any failing draft)
- hidden SRS replay (dry run by default; runs automatically after every event batch): `cd server; uv run python scripts/derive_srs.py [--db PATH] [--rebase] [--check] [--apply]`
- generate a batch: `/generate-batch` skill (`.claude/skills/generate-batch/`)
- word sets: edit `content/seed/word_sets.json`, then `cd server; uv run python scripts/ingest_episodes.py --seed` (creates lexemes; served at `GET /api/word-sets`)

## Conventions
- Lexemes keyed by (lemma, pos). Never key vocabulary by surface form.
- Grammar points keyed by stable code (e.g. `G.KIRO_HADA`), mapped to
  Kiwi morpheme patterns.
- Events are append-only, UUID-keyed, idempotent on sync.
