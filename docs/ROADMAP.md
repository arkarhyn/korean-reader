# ROADMAP

Minimum usable version = Stages 1-6. One stage per Claude Code session.
Mark the current stage with `<- CURRENT`.

## Stage 1 -- Spec and data model (claude.ai Project)  DONE
SPEC.md, DATA_MODEL.md, DECISIONS.md, ROADMAP.md, CLAUDE.md written.

## Stage 2 -- Repo scaffold + analyzer pipeline  <- CURRENT
- Scaffold `server/`, `web/`, `content/`, `legacy/`, `docs/`.
- Python env; install kiwipiepy; `analyze(text) -> tokens` returning
  (surface span, lemma, pos) for content words and grammar morphemes.
- krdict lookup client with local cache (API key in `.env`, gitignored).
- Port the 2 legacy readers (토요일 아침, 호랑이와 곶감) into episode JSON.
- Load `content/seed/flagged_vocab.json` (lexemes -> learning; particles ->
  grammar codes).
**Accept:** golden tests: every content token in both legacy readers maps to
the correct (lemma, pos); 했어요 / 했어요. resolve to 하다; coverage function
returns a number for each reader. `pytest` green.

## Stage 3 -- Server API + DB + reader UI with tap logging
- SQLite schema per DATA_MODEL; Alembic migrations.
- Endpoints: episodes list/get, events batch POST (idempotent), sync pull.
- Web: port legacy design (parchment palette, Nanum Myeongjo / Gowun Batang),
  reader view, tap popover (EN/JP gloss, Hanja, TTS), translation toggle,
  questions, responsive phone/laptop.
- Offline: Dexie cache + event queue. Resolve DECISIONS O1 (HTTPS).
**Accept:** read an episode on iPhone over VPN, go offline, tap words,
reconnect, events land once on server.

## Stage 4 -- Placement
- Grammar check (HTSK 1-28 points), frequency-band yes/no with pseudowords,
  3-4 calibration passages.
- Fit initial lexeme / grammar states.
**Accept:** placement completes in <= 25 min on phone; produces states;
a calibration passage re-scored with the fitted model lands within +/- 2%
of observed tap rate.

## Stage 5 -- Generator loop (`/generate-batch` in Claude Code)
- Design session first (Project): STORY_BIBLE.md.
- `GET /export/generation-context`; coverage CLI; swap loop; second-pass
  review prompt; ingest script; "sounds off" flags surfaced.
**Accept:** batch of 5 episodes all in 95-98% band, target grammar 4-6x each,
due words included; Austin reads 3 and rates naturalness >= 4/5.

## Stage 6 -- Hidden SRS
- Event -> FSRS derivation job (words + grammar); replayable.
- Meaning checks (~1 in 5 due words); generator due-weighting.
- Optional Quick review (tap-only, stored context + audio).
**Accept:** replaying the event log reproduces identical states; due words
appear in next batch; no backlog UI exists.

## Stage 7 -- Ingest
- Paste / .srt / .vtt; coverage report; pre-teach primer; one-tap mine.

## Stage 8 -- Grammar track
- Design session first (Project): SYLLABUS_MAP.md (HTSK lesson -> code ->
  JP parallel -> Kiwi pattern).
- Lesson cards + select-only drills; generator grammar gating.

## Stage 9 -- Audio polish
- Shadowing loop mode, speed control, TTS cache; provider swap hook.
