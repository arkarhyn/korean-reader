# STATUS

## 2026-10-05 -- Stage 8 grammar track (Claude Code, built straight through; DECISIONS 92-97)
**Done (branch `stage-8`, worktree `.claude/worktrees/stage-8`, on top of `stage-6`):**
- SYLLABUS_MAP: Kiwi patterns for all 54 L1-28 points + 36 new points (HTSK L29-50, L34
  skipped; threads -는데 / -(으)니까 / -더니 / -기로 하다 pulled forward with `teach_order`).
  Doc tables are rendered from `content/seed/grammar_points.json`. **L29+ rows await
  Austin's review** (labels, JA parallels, which points to merge/split).
- 8 lesson cards (`content/grammar/lessons/`): 동안, 에 대해, -아/어지다, 위해, -스럽다,
  ㅎ irregular, -기, -(으)ㅁ. 2 examples + 4 select-only drills each.
- Server: migration 0005 (`grammar_point.teach_order`, `lesson`), seed validates lessons,
  sync pull sends `grammar` (full list), replay handles `grammar_lesson_complete`
  (new -> introduced, first review from the drill score), checker gating (tested-new or
  lesson-waiting = fail, untested L29+ = `~` warning, new target needs a lesson),
  context `next_new_targets` / `grammar_untested`; `/generate-batch` skill updated.
- Web: `/grammar` list (Library foot "문법 · Grammar"), `/grammar/:code` lesson flow,
  Up next gate ("Grammar first: <point>" + "Skip to the episode").
- Tests: server 179 passed (4 skipped), web 54 passed, tsc + build OK.
- Checked on a copy of the live DB (876 events): migration + seed + re-ingest change no SRS
  rows; replay stable. In Chrome: list -> 동안 lesson -> 4 drills -> 1/4 -> events synced,
  동안 introduced (S 0.21 d); with S01E005's target set to G.E_DAEHAE (copy only) the Up next
  card showed the gate, the lesson ended in "Read the episode" -> /read/S01E005, gate gone.
  Existing S01 episodes: only real issues flagged (ㅎ irregular 그래요/빨간 = blocked until
  that lesson is done; L29+ forms as warnings).

**Deployed 2026-10-05 (Austin OK'd):** live DB backed up to
`%TEMP%\kr5\live_backup_pre_stage8.db` (886 events, integrity ok, at 0004); service stopped;
`stage-6` fast-forwarded to `stage-8` (b19c0a7); migration 0005 + `ingest_episodes.py --seed`
(srs: 0 rows changed; replay stable); web rebuilt; service started; health OK (sync pull: 10
episodes, 92 grammar points / 8 lessons, 20 review items; `/grammar` 200; podcasts intact).
Rollback: stop service, restore the backup, reset `stage-6` to 68ad101, rebuild web, start.

**Next:** Austin does lessons from `/grammar` (each one unblocks its point for the
generator) and reviews the L29+ map rows; then `/generate-batch` (first batch with a new
target: G.DONGAN or whatever is first in `next_new_targets`; also closes Stage 6/7 checks).

**Open issues:**
- Lessons use 아버님/어머님 from Ethan (fine for lessons, ahead of the story timeline).
- Some distractors are deliberately ungrammatical conjugations (빨갛아, 좋면).
- Three drills test a contrasting point as the answer (때, 때문에, -는 것 -> 걸).
- Isolated honorific verbs can misparse in Kiwi (주무세요 -> 주무/NNG); -세요 still matches.
- 그래/어때 count as ㅎ irregular: blocked for the generator until that lesson is done.

## 2026-10-05 -- Stage 7 wrap-up (same session, after deploy)
**Deployed (web-only follow-ups, stage-6 = stage-7):** live coverage in the Library and
`/api/podcasts` (DECISIONS 89); placement resume card Dismiss when already placed; Quick
review autoplay toggle; story read-aloud cursor (◀ ↻ ▶, Space/→/←/R, margin markers;
DECISIONS 90); per-character voice profiles + voice picker (DECISIONS 91). Podcast
coverage refreshed after Austin's vocab pass (mean 70%, best part 80%).

**Next (Austin):** Stage 8, grammar track, in a NEW session. Start with the design
step: extend `docs/SYLLABUS_MAP.md` past lesson 28 (current position ~L29) and fill Kiwi
patterns for the existing rows; map only, no HowToStudyKorean text copied (SPEC 3.4).
Phase C (paste/.srt ingest) is deferred. Still pending: one `/generate-batch` run (with a
primer requested first) closes Stage 6's and Stage 7's last acceptance checks.

**Open issues:** ~25% of podcast lexemes lack glosses (gloss-fill pass proposed); see the
Stage 7 entry below for the rest.

## 2026-10-05 -- Stage 7 Phases A + B (Claude Code)
**Done (branch `stage-7` = `stage-6` + podcast work, worktree `.claude/worktrees/podcast-transcripts`):**
- Phase A (`corpus/podcasts/didi-taewoong/`): 33 Didi & Taewoong episodes downloaded
  (yt-dlp; 23 with creator subtitles), 23 speaker-labeled and split into 106 ~10-min parts
  (`prep.py`), coverage ranking, `podcast-common` word set (76 words, +9-11 pts coverage).
- Phase B (DECISIONS 84-88): migration 0004 (`episode.media`, `episode_paragraph.meta`),
  `podcast` series, `app/podcasts.py` + `scripts/ingest_podcasts.py`, line-level context
  sentences, due-only grading for podcast completions, Quick review prefers story sentences,
  `/api/podcasts`, podcasts out of sync pull, `primer_request` -> `primer_requests` in the
  generation context (+ checker bands, skill step 2b). Web: `useWordTaps` + `WordSpans`
  extracted from the Reader (no behavior change), Listen tab (`/listen`, `/listen/:id`) with
  YouTube IFrame player, line follow, seek, pause-on-tap, "Learn this", primer button.
- Tests: server 145 passed (4 skipped), web 38 passed, tsc clean, build OK.
- Checked on a copy of the live DB: all 106 parts ingest in ~20 s (coverage 56-73%, mean
  65%); replay stable; in Chrome the list, part page, word tap, Learn this and finish all
  worked, and finishing a 289-word part created exactly 1 card (the mined word).
  Playback/line follow not seen in the browser (the Chrome window was hidden, so video
  can't play); `activeLineAt` is unit-tested.

**Deployed 2026-10-05 (Austin OK'd):** live DB backed up to
`%TEMP%\kr5\live_backup_pre_stage7.db` (827 events, integrity ok); service stopped; `stage-6`
fast-forwarded to `stage-7` (d78ef30); `ingest_episodes.py --seed` (migration 0004, word set,
host names) + `ingest_podcasts.py --publish` (106 parts, 20 s; srs: 0 rows changed; replay
stable); web rebuilt; service started; health OK (`/api/podcasts` 23 episodes / 106 parts,
sync pull 10 story episodes, no podcasts; `/listen` 200).
Rollback: stop service, restore the backup, reset `stage-6` to 89708ae, rebuild web, start.

**Next:** Austin listens to a part on the phone (check line follow + video inline); request
a primer, then `/generate-batch` (also Stage 6's pending acceptance). Then Phase C.

**Open issues:**
- 1,557 of 6,152 podcast lexemes (25%) have no gloss, including common ones (그래도, 완전,
  이렇게, 어떻게, 아니면): local-dump POS mismatches + spoken forms. Fix: a gloss pass in a
  Claude Code session (`gloss_source = llm`, SPEC 5) or POS fallbacks in the lookup.
- Some subtitle cues hold 2-3 speakers (01 40-50 min, 05 30-36 min, 18 9-18 min); labels
  there are approximate. 10 auto-caption episodes are not ingested.
- The embedded player stops when the iPhone locks (YouTube embed limit).

## 2026-10-05 -- Stage 6 (Claude Code)
**Done (branch `stage-6-srs`, worktree `.claude/worktrees/stage-6-srs`, on top of `stage-6`):**
- Hidden SRS (`server/app/srs.py`): baseline columns (migration 0003) + full replay of
  the event log after every event batch, placement fit and ingest; py-fsrs, no fuzz.
  Rules in DECISIONS 75-83: tapped -> Again, soft lapse for known words (Austin), untapped
  new word -> Good, due -> Good, meaning checks, graduation at S >= 21 d, grammar from
  grammar_check only. Due / counts-known = before/after last_review + stability.
- Generator: `due` ordered by retrievability (then unreviewed by rank) with
  retrievability in the context; due grammar first in `suggested_targets`; checker wants
  ~1 meaning check per 5 due words and prints batch coverage of the top-15 due; skill updated.
- Ingest: meaning_check target_ref -> lexeme id; question ids stable across re-ingest;
  `context_sentence` rows with the word's span.
- Quick review: `review_items` in sync pull, `/review` (sentence + TTS + 3 meanings),
  `review_answer` event, "복습" link in the Library only when items exist, no counts.
- Reader: known tint follows SPEC 7 (learning until R 0.9); `episode_complete.lexeme_ids`,
  `question_answer.kind/target_ref`, `set_state.undo`.
- `scripts/derive_srs.py` (dry run / `--rebase` / `--check` / `--apply`).
- Tests: server 135 passed (incl. the acceptance test: random out-of-order API batches ==
  one-shot replay; derive twice changes nothing), web 33 passed, tsc clean, build OK.
- Checked on a copy of the live DB: rebase + derive 40 ms, replay stable; re-ingest
  changes nothing; in Chrome a Quick review answer graded 놓치다 (Good, S 2.3 d), and
  finishing S01E004 with one tap graded 텃밭 Again and 4 untapped new words Good.

**Live dry run (copy of the live DB, not applied):** 594 -> 603 words count as known.
New ones (read untapped, known for ~2 days, then due): 결혼식, 긴장, 넣다, 당신, 받다, 봉투,
쓰다, 전, 축의금. One known word demoted by a tap (soft lapse): 길다. 94 due; top:
부르다, 긴장하다, 곧, 그러다, 그릇, 댁, 데려오다, 또, 모두, 식탁, 하루, 단톡방, then
placement `seen` words (대하다, 보이다, 가지다...).

**Deployed 2026-10-05 (Austin OK'd the dry run):** `stage-6` fast-forwarded to
`stage-6-srs`; live DB backed up to `%TEMP%\kr5\live_backup_pre_stage6.db`; service stopped;
`derive_srs.py --rebase --check --apply` (migration 0003; replay stable; 599 counts-known,
98 due, top: 그릇, 댁, 데려오다, 단톡방, 또, 부르다, 긴장하다, 곧...); all episodes re-ingested
(srs: 0 rows changed); web rebuilt; service started; health OK, sync pull serves 20 review items.
Rollback: stop service, restore the backup, reset `stage-6` to a0fd0cf, rebuild web, start.

**Next:** `/generate-batch` (acceptance: due words appear in the batch; the
checker's `batch:` line). Stage 6 is DONE once that batch passes.

**Open issues:**
- Context sentences from legacy episodes carry the whole paragraph's English.
- 94 due at first: never-reviewed placement `seen` words wait behind reviewed ones; the
  generator only weaves 1-3 per episode (by design, no backlog).
- Old question answers to S01E003-005 from before their regeneration point at deleted
  questions and are skipped by the replay.

## 2026-10-04 -- Stage 5 (Claude Code, overnight)
**Done (branch `stage-5`):**
- Popover "알아요" (mark known; "✓ 알아요 · 취소" undoes within the visit) and
  "잘못 눌렀어요" (un-tap a mistap). `set_state` is applied by the server on receipt
  (`app/events.py`, replayable); new `word_untap` event. Checked in Chrome
  against a DB copy: mark -> sync -> server known 419->420, undo -> 419, un-tap
  logged, tap highlight cleared.
- `GET /api/export/generation-context` + `scripts/export_context.py`;
  `scripts/coverage_check.py` (coverage, new/due words, target grammar count,
  length, `new`-grammar warnings); `episode.summary` (migration 0002); ingest
  fills `new_lexemes` / `review_lexemes`.
- Grammar pattern matcher (`app/analyzer/patterns.py`) with kiwi_pattern for
  the 5 targets + the `new` points. Story names as Kiwi user words, known for
  coverage, glossed (`content/seed/proper_nouns.json`). Known-set tag aliases
  (DECISIONS 59).
- `/generate-batch` skill + second-pass reviewer prompt (`.claude/skills/generate-batch/`).
- **Batch S01E001-005 published live** (95.1-95.6%, 3-6 new words each,
  target grammar 4-6x, 1-2 due words each). Second-pass review by a fresh
  subagent (scores 4 / 4 / 3.5 / 4 / 2.5): fixed a cultural error in E3 (the
  bride's parents receive 축의금, they don't give it), early address terms
  (어머님, 서현 씨 before Ep 7), and E5's drill-like -지 못하다 in casual speech
  (now 못 in speech, long form in narration). Canon log appended to STORY_BIBLE.
- Later the same day (Austin's requests): Library reorganized into an "up next"
  card + season / side-story / practice sections (DECISIONS 63); popover
  buttons now in English (DECISIONS 64); known-word tint with a toggle and
  "I forgot this" (DECISIONS 65-66). Server 109 tests, web 22.
- Deployed: live DB backed up, migrated to 0002, seeded, episodes ingested,
  web/dist rebuilt, service restarted. Server 108 tests, web 17, tsc clean.

**Acceptance: PASSED.** Checker criteria met; Austin read the batch and rated
naturalness 4+ (DECISIONS 67). Stage 5 DONE.

**Side load (same day): word sets** -- `/words` in the app: 21 themed
checklists (numbers, days, months, food, verbs...) + a frequency walk over the
NIKL list. Confirmed words become known via `set_state` and feed the next
batch (DECISIONS 68-69). Server 125 tests, web 25. Deployed (live DB backup
`%TEMP%\kr5\live_backup_pre_wordsets.db`).

**Read this first (Austin):** the generator writes against the DB's known set,
which placement left very narrow (419 words; 응, 괜찮다, 언니, 알다, 가족, 좋아하다
all count as unknown). So these episodes are simpler than your real level, and
some "new" words aren't new to you. Tap **I know this word** on every word you know as
you read -- each tap widens what the next batch can use (DECISIONS 60).

- 2026-10-05: read marks (✓ read / Up next) now sync between devices via
  `completed` in sync pull (DECISIONS 70). Server 126 tests, web 26.

- 2026-10-05: S01E003-005 regenerated against 597 known words (95.1-95.6%),
  reviewed (4/5 each), published; all S01 episodes now one speaker per line;
  reader shows speaker labels and an inline EN toggle (DECISIONS 71-72).
  Speaker names are color-coded per character; dialogue has a hanging indent
  and narration extra spacing (DECISIONS 73-74).
  Server 127 tests, web 29. Live DB backup `%TEMP%\kr5\live_backup_pre_regen.db`.

**Next:** Austin works through some word sets, then the next `/generate-batch`
(must resolve E5's leave cliffhanger; vary days/times now that weekday words
can be confirmed). Then Stage 6 (hidden SRS).

**Open issues:**
- Live DB backups: `%TEMP%\kr5\live_backup_pre_stage5.db`,
  `%TEMP%\kr5\live_backup_pre_publish.db` (bash `$TEMP/kr5`).
- NIKL import oddities: 문 is stored as NNP (rank 469); 달 (month) is NNB but Kiwi
  tags 다음 달 as NNG "moon"; 제일 splits into 제 + 일/NR; 이렇게 is MAG with no
  lexeme; 그날 / 다음 주말 parse inconsistently.
- Earlier-batch new words (고기, 결혼식, 가족...) stay unknown until tapped
  알아요 or Stage 6, so they eat each later episode's 3-6 new-word budget.
- 단톡방 gloss is `llm` (no krdict entry).
- Carried over from Stage 4: rare-rank compounds, -성/-적/-화 derived forms,
  낡다 no gloss, krdict API down, light theme, iOS ko-KR voice, key rotation.

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
