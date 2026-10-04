# STATUS

## 2026-10-03 -- Stage 4 (Claude Code)
**Done (branch `stage-4`):**
- Grammar points for HTSK 1-28 (`content/seed/grammar_points.json`, 54 codes)
  seeded via `seed()`; SYLLABUS_MAP rows L1-28.
- NIKL learner list: `scripts/fetch_nikl_vocab.py`, `app/nikl.py`,
  `scripts/import_nikl.py`. Live DB has 5,712 ranked lexemes (~99% glossed).
- Placement content: 104 grammar sentences, vocab test
  (`scripts/build_placement.py`: 96 real + 24 pseudo), 3 calibration passages
  (`content/placement/calibration/`, easy A -> A+B -> B/C + 23% off-list).
- `app/placement/` (fit, items, service), `GET /api/placement`,
  `POST /api/placement/fit`, `scripts/placement_report.py`.
- Web `/placement`: grammar cards -> vocab cards -> calibration passages in the
  reader (placement mode) with 1-5 rating -> fit summary. Resume and Undo; the
  Library shows a start/continue card and later "Redo placement"; placement
  passages hidden from the Library.
- Tests: server 90 passed, web 14 passed, `tsc` clean, build OK.
- Laptop run-through in Chrome against a DB copy: two full attempts, all 328
  events landed once, fit summary rendered, Library coverage updated after
  sync. Fixed during the run: the double-tap guard dropped fast taps, and finish
  could read stale taps.
- Deployed: calibration passages + grammar points in the live DB, service
  restarted, `/api/placement` live on :8443, web/dist rebuilt.
- Acceptance criterion changed to the 95% predictive interval (DECISIONS 50).

**Closed 2026-10-04 (DECISIONS 53):** Austin ran placement on the iPhone.
States written: 419 known, 79 seen; grammar 31 solid, 17 practicing, 6 new
(G.DONGAN, G.EOJIDA, G.E_DAEHAE, G.IRREG_H, G.SEUREOPDA, G.WIHAE). Calibration
missed on 2 of 3 passages, and time ran ~40 min of answering. Accepted: the
frequency-rank guess is rough for Austin's drama/textbook vocabulary, and
reading data will correct it.

**Next:** Stage 5. First a claude.ai Project design session for
STORY_BIBLE.md (O2: names, setting, cast, Season 1 arc). Then the Claude Code
session: popover "알아요" + un-tap (DECISIONS 54), `GET
/export/generation-context`, coverage CLI, `/generate-batch`.

**Open issues:**
- The live DB backup from before the NIKL import is at
  `%TEMP%\kr_backup_stage4.db` (bash `$TEMP`).
- Lexemes outside the NIKL list get one "rare" rank, including easy
  compounds (일기장, 시골집). Could derive a rank from components or krdict grade.
- Derived forms in the NIKL list that the analyzer splits (-성, -적, -화) never
  match tokens; only their bases count.
- 낡다 has no gloss (krdict lookup miss; new lexeme from cal-3).
- Carried over: krdict API down (local dump in use); light theme not
  eyeballed; iOS ko-KR voice untested; krdict key rotation.

## 2026-10-03 -- Stage 3 (Claude Code)
**Done:**
- SQLite schema (`server/app/db/models.py`) per DATA_MODEL + Alembic
  (`server/migrations/`, revision 0001). Additions logged in DECISIONS 35.
- Ingest (`app/ingest.py`, `scripts/ingest_episodes.py`): analyzer tokens ->
  lexeme ids, krdict glosses, coverage, questions; seed loads grammar points
  + 12 flagged lexemes (learning) + 2 particle grammar states (introduced).
  Both legacy episodes published in `server/data/korean_reader.db`.
- API: `GET /api/episodes`, `GET /api/episodes/{id}`, `POST /api/events/batch`
  (idempotent), `GET /api/sync/pull?since=`; FastAPI serves `web/dist` with
  SPA fallback.
- `web/`: Vite + React 19 + TS 7 + Tailwind 4 + vite-plugin-pwa + Dexie.
  Library, reader (tap popover with EN/JP/Hanja/TTS, per-paragraph English
  toggle, "sounds off" sentence flag), tap-only questions, finish ->
  `episode_complete`. Offline event queue + sync (open / foreground / online /
  5 min / manual). Parchment theme + dark variant, PWA icons.
- `scripts/serve.py` (migrate + uvicorn, TLS from env),
  `scripts/install_service.ps1` (NSSM service, tailscale cert, firewall,
  renewal task), `scripts/renew_cert.ps1`.
- Tests: server 67 passed (offline); web 9 passed; `tsc` clean; build OK.
- Verified in Chrome on laptop: library + reader + taps; server stopped ->
  page loads from service worker, taps queue; server restarted -> queue
  flushed in one batch, `event` rows == distinct ids.

- Service installed (NSSM `korean-reader`, https on :8443, tailscale cert,
  renewal task). **Acceptance passed on iPhone:** offline taps landed once
  after reconnect (Austin, 2026-10-03).

- Added after acceptance: local krdict dump index
  (`scripts/build_krdict_local.py`, `app/krdict/local.py`), gloss lookup
  chain in ingest; 73 server tests pass.

**Next:** Stage 4 (placement). Inputs already chosen (DECISIONS 43):
Claude drafts HTSK 1-28 SYLLABUS_MAP rows -> Austin reviews -> test
sentences; vocab bands from the NIKL learner list (needs download + parser);
Claude writes 3-4 calibration passages.

**Open issues:**
- krdict API unreachable since mid-ingest on 2026-10-03 (refused from
  outside too, so not our setup). Glosses now come from the local krdict
  dump (DECISIONS 42): 161/167 lexemes glossed. Remaining 6 have no usable
  entry: compounds/derived (산책시키다, 애견용품), 초코 (name), 알람, and
  contraction-only entries (그래도, 어떡하다). Compounds could fall back to
  component glosses later. The live krdict pytest fails while the API is down.
- Coverage shows 0% everywhere: no lexeme is `known` until placement (Stage 4).
- `legacy_vocab.json` still not imported (DECISIONS 28).
- Light theme not yet eyeballed (dev machine is in dark mode).
- iOS: Web Speech ko-KR voice availability on the iPhone untested.
- Font slices are cached only after first render online; a never-seen glyph
  falls back to the system serif offline.
- The krdict key was pasted in chat on 2026-10-03; consider regenerating it.

## 2026-10-03 -- Stage 2 (Claude Code)
**Done:**
- `server/` uv project (Python 3.12; kiwipiepy 0.24, fastapi, sqlalchemy,
  fsrs, httpx, pydantic). `GET /health` only.
- Analyzer `app.analyzer.analyze(text) -> [Token(start, end, surface, lemma,
  pos, kind, grammar_code)]`. Ported legacy rules (irregular tags, compound
  nouns, noun+하 derivation), plus: XPN prefixes, XR+하, -드리다 humble verbs,
  the 아는 -> 알다 misparse fix, 있다 canonical VA, and negation, auxiliaries
  and copula as grammar. `lemmatize(word)` for single words.
- `app.coverage.coverage()` / `unknown_lemmas()`: running content tokens.
- krdict client + SQLite cache (`server/data/krdict_cache.sqlite`); needs a
  browser-ish/httpx UA (curl's default UA is blocked by their WAF). Fixtures
  recorded from the live API.
- Episodes `content/episodes/legacy/legacy-00{1,2}.json` (passages #20/#21,
  English translations and 3 comprehension questions each).
- Hand-reviewed golden files `server/tests/golden/` (143 + 148 content tokens).
- `content/seed/legacy_vocab.json`: 521 legacy rows -> 471 lexemes
  (78 learning) + 18 unresolved for manual review.
- `pytest`: 53 passed (incl. live krdict).
- `web/` is a README placeholder (Node not installed).

**Environment ready for Stage 3 (verified 2026-10-03):**
- Node v24.21.0 / npm 11.19.0 (choco).
- Tailscale 1.98.8 on desktop + iPhone. Desktop hostname
  `arka18-desktop.tail91f88.ts.net`; MagicDNS + HTTPS certificates enabled,
  so `tailscale cert` should work. Planned
  `PUBLIC_BASE_URL=https://arka18-desktop.tail91f88.ts.net:8443`.
- Leaning toward O1 = `tailscale cert` and O4 = native Windows service; not
  confirmed yet. Austin doesn't need the service set up right away.

**Next:** Stage 3. SQLite schema + Alembic, ingest
legacy episodes (tokens -> lexeme ids via analyzer + krdict glosses), API,
reader UI. Resolve O1 (HTTPS) and O4 (deploy target).

**Open issues:**
- Grammar codes exist only for a few particles plus negation. Multi-morpheme
  patterns (-ㄹ 수 있다, -ㄹ 거예요, -고 싶다) are unmatched until
  SYLLABUS_MAP (Stage 8). Their 수/거 (NNB) currently count as content.
- Ambiguous bare dictionary forms: 쓰다 alone -> VA (bitter). Seed import
  should confirm POS against krdict.
- `legacy_vocab.json` unresolved list (phrases like 사진을 찍다, plus 싶다/않다)
  needs a manual pass before import.
- The krdict key was pasted in chat on 2026-10-03; consider regenerating it.
- DECISIONS O1-O4 still open.


## 2026-10-03 -- Stage 1 (design, claude.ai Project)
**Done:** handoff kit written (CLAUDE.md, SPEC, DATA_MODEL, DECISIONS,
ROADMAP, STATUS, LEARNER_PROFILE, STORY_BIBLE seed, SYLLABUS_MAP seed,
.gitignore, .env.example, content/seed/flagged_vocab.json).
**Next:** Stage 2 in Claude Code -- scaffold + Kiwi analyzer + port legacy
readers + golden tests.
**Open issues:** DECISIONS O1 (iOS HTTPS), O2 (story bible), O3 (kanji set),
O4 (desktop deploy target).
**Needs from Austin before Stage 2:** krdict open API key
(krdict.korean.go.kr -> 오픈 API); copy `korean_graded_readers.jsx` into
`legacy/`; install Tailscale on desktop + iPhone (before Stage 3).
