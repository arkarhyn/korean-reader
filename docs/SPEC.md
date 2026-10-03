# SPEC -- korean-reader v1

## 1. Purpose
Remove the two failure modes of existing Korean content: material far above
comprehension (slow, exhausting) and material far below it (boring). Every
generated passage targets 95-98% known-word coverage, introduces a controlled
number of new words, and advances a deliberate grammar progression.

## 2. User and devices
- Single user (Austin). Japanese background (strong reading); Korean grammar
  roughly ahead of vocabulary.
- Laptop: structured grammar track, ingest, triggering generation batches.
- iPhone: reading, listening, optional quick review. Select/tap only.
- Both views from one responsive PWA.

## 3. Core loops

### 3.1 Read loop (primary)
1. App shows next episode with a coverage preview
   ("97% known - 4 new words - target grammar: -기로 하다").
2. User reads. Tapping a word opens a popover: dictionary form, EN gloss,
   JP gloss, Hanja (if Sino-Korean), word audio.
3. Translation toggle per paragraph (off by default).
4. End of episode: 3-6 tap-only questions (comprehension + embedded meaning
   checks + grammar checks).
5. Events (taps, answers, completion) feed the hidden SRS.

### 3.2 Hidden SRS (no flashcards)
- FSRS schedules lexemes AND grammar points.
- A "review" is an encounter in a reader. Due items are prioritized by the
  generator for the next batch.
- Grading on episode completion, for each DUE item present:
  - word tapped -> Again
  - word not tapped -> Good
  - meaning check answered correctly -> Good (Easy if not tapped and fast)
  - meaning check wrong -> Again
- Non-due items seen without a tap -> exposure count only, no FSRS review
  (prevents inflated stability).
- About 1 in 5 due words per episode also gets a 3-option meaning check.
- No daily queue. Missed days do not create a backlog screen.
- Optional "Quick review": short tap-only session from the last-synced due
  list, using stored context sentences + audio. No streaks.

### 3.3 Ingest loop (outside content)
- Paste text or upload subtitle file (.srt/.vtt/.txt).
- Server analyzes -> coverage report (known %, unknown lemma list sorted by
  frequency and repetition in the text).
- Options:
  - Pre-teach: queue a short primer reader on the top 5-10 unknowns.
  - Mine: one tap per word -> state `learning`, source sentence stored as
    context.
  - Read raw: tap-through with full glosses.
- Ingested text stays private on the home server; never redistributed.

### 3.4 Grammar track (structured)
- Syllabus map from HowToStudyKorean progression (lesson -> grammar point ->
  Japanese parallel -> Kiwi pattern). Map only; no HTSK text copied in.
- New grammar point = lesson card before its first episode:
  Japanese parallel and where it differs -> 2 examples -> 3-5 select-only
  drills.
- Generator only uses grammar at state >= `introduced`, plus exactly one
  target point per episode (appearing 4-6 times).

### 3.5 Placement (first run)
1. Grammar check: 2 sentences per HTSK lesson 1-28 grammar point,
   user marks "got it" / "fuzzy". ~10 min.
2. Vocab yes/no test sampled across frequency bands, with pseudowords to
   correct for overclaiming. ~5 min.
3. 3-4 calibration passages at different estimated coverage; user taps only
   unknowns; self-rates comprehension 1-5.
4. Model fit -> initial lexeme states + coverage calibration.
No HTSK vocab priors.

## 4. Content
- Serialized family slice-of-life (see STORY_BIBLE.md, written in Stage 5
  design session).
- Register switching is a core thread: 반말 with girlfriend; 해요체/합니다체,
  -(으)시-, humble verbs, honorific nouns with her parents.
- Episodes ~400-700 Korean characters; 1 target grammar point; 3-6 new words;
  due reviews woven in.
- Formats vary: narration, dialogue, KakaoTalk-style chats, diary, phone
  calls, occasional parent-POV side stories, occasional folktale side stories.
- Every passage tagged with register(s).

## 5. Generation (no API billing)
- Runs inside a Claude Code session via a `/generate-batch` skill/command:
  1. Fetch generation context from server (`GET /export/generation-context`):
     known/learning lexemes, due items, grammar states, next target grammar,
     story bible, recent episode summaries.
  2. Claude drafts N episodes as JSON into `content/episodes/`.
  3. Coverage tool analyzes each draft; out-of-band words reported.
  4. Claude swaps offending words, re-checks until 95-98% or flags.
  5. Second-pass review (separate prompt): naturalness, register
     consistency, target grammar density, continuity.
  6. Ingest script loads passing episodes into DB as `published`.
- Glosses come from dictionary data (krdict), not the LLM; LLM fills gaps
  only when the dictionary has no entry, marked `gloss_source = llm`.

## 6. Audio
- v1: system TTS (Web Speech API, ko-KR voice). Behind a `TtsProvider`
  interface so a cloud provider can replace it later.
- Shadowing mode: loop a 60-90 s segment, 0.75x / 1.0x speed.

## 7. Coverage definition
- Count content tokens only (particles, endings, copula excluded; grammar
  tracked separately).
- Known = lexeme state `known`, or `learning` with retrievability >= 0.9,
  or `ignored`, or proper noun in story bible.
- Sino-Korean transparency: lexeme with Hanja whose characters are all in the
  user's kanji set counts 0.5 known if otherwise unknown. (Kanji set
  bootstrapped later; off until then.)
- Target band: 95-98%. Below 95% -> revise. Above 98% -> add new words.

## 8. Feedback
- "This sounds off" button on any sentence -> event logged; flagged sentences
  surfaced in next generation session for regeneration.

## 9. Hosting and sync
- Home desktop (always on): FastAPI + SQLite.
- Desktop is on 24/7. Remote access via Tailscale (preferred) or the
  existing SoftEther/OpenVPN setup; WireGuard later. Transport-agnostic:
  app only knows a base URL.
- Offline-first clients: episodes + user state cached in IndexedDB; events
  queued and synced on app open / foreground / manual sync.
- Sync triggers: app open, app foreground, every 5 min while open, manual.
  (iOS PWAs cannot sync reliably in the background; the server side is
  always reachable, so this is enough.)
- PWA requires HTTPS for service workers on iOS: see DECISIONS O1.
- Learner context for generation lives in `docs/LEARNER_PROFILE.md`.

## 10. Out of scope for v1
Speaking/production practice, multi-user, Ollama, paid TTS, Anki export,
visible streaks or gamified scores.
