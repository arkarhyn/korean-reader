# DECISIONS

Append-only. Format: date - decision - rejected alternative - reason.
Do not reverse an entry without asking Austin.

## 2026-10-03 (design sessions in claude.ai Project)

1. **Build in Claude Code; claude.ai Project for design/QA.**
   Rejected: single-file claude.ai artifact. Reason: multi-file app, needs
   tests, analyzer, DB, git history.
2. **Repo outside OneDrive; private GitHub backup.**
   Rejected: OneDrive path. Reason: sync locks on node_modules / .git.
3. **Track vocabulary by (lemma, pos) via Kiwi; grammar as a separate system.**
   Rejected: surface-form glossary (legacy JSX). Reason: agglutination makes
   surface forms explode (했어요 / 했어요. duplicates).
4. **Coverage target 95-98% known content words.**
   Rejected: fixed difficulty levels. Reason: measurable, matches
   comprehensible-input research (Hu & Nation 2000; Nation 2006).
5. **Generation inside Claude Code sessions on subscription.**
   Rejected: in-app Anthropic API (per-use billing); Ollama as author
   (RTX 2060 / ~7-8B models too weak for natural Korean).
6. **No Ollama in v1.** Revisit only if on-demand generation away from a
   Claude session becomes a real need.
7. **Hidden SRS (FSRS) for words and grammar; review = encounter in reader;
   grading from tap / no-tap + embedded meaning checks.**
   Rejected: visible flashcards. Reason: card creation and daily grind were
   the pain points with Anki.
8. **FSRS state derived from append-only event log.**
   Rejected: mutate state directly on tap. Reason: scoring rules will change;
   replay must be possible.
9. **Placement: grammar check over HTSK 1-28 + frequency-band vocab test
   with pseudowords + calibration passages. No HTSK vocab priors.**
   Reason: Austin skipped HTSK vocab sections.
10. **Ingest mode for outside content (coverage report, pre-teach, mine).**
11. **Structured grammar track from HTSK syllabus map only; no HTSK text
    copied.** Reason: copyright; private personal use.
12. **Serialized family slice-of-life; register switching as core thread.**
    Reason: real goal is talking with girlfriend (반말) and her parents
    (honorific/polite registers).
13. **Protagonist loosely echoes Austin** (Japanese speaker learning Korean,
    girlfriend is a Korean-American who understands but is rusty speaking).
    Fictional names and details. Rejected: generic protagonist. Reason: enables
    in-story Japanese-parallel moments and turns episodes into rehearsals for
    real conversations.
14. **Hosting: home desktop (always on 24/7, confirmed), FastAPI + SQLite.**
    Rejected: Supabase (free tier pauses on inactivity), Cloudflare D1
    (data leaves home). 
15. **Remote access: Tailscale preferred, SoftEther/OpenVPN as fallback;
    WireGuard later.** App stays transport-agnostic (only knows a base URL).
    Reason: Tailscale runs in the background on iPhone (no manual connect
    before sync) and can issue a trusted HTTPS cert for the desktop's
    tailnet hostname. Updated 2026-10-03.
16. **Offline-first clients (IndexedDB + event queue).**
17. **TTS: system voices first, behind TtsProvider interface.**
18. **Second-pass Claude review + "sounds off" button.**
19. **Stack:** Python/FastAPI/SQLAlchemy/kiwipiepy/py-fsrs server;
    React/TS/Vite/PWA/Tailwind/Dexie client.
    Reason: Kiwi's mature binding is Python; keeps analyzer server-side.
20. **Seed data from prior study:** flagged vocabulary from earlier reader
    sessions starts at state `learning` (content/seed/flagged_vocab.json).
21. **Background generation is allowed** because the desktop is 24/7, but
    v1 generation still runs in an interactive Claude Code session.
22. **Secrets never committed:** krdict key in `.env`; TLS keys and any CA
    material live outside the repo, referenced by path.

## 2026-10-03 (Stage 2, Claude Code)

23. **Legacy readers = Graded-Reader-Project passages #20 (강아지를 키우고
    싶어요) and #21 (시험 날 아침)** as `legacy-001` / `legacy-002`.
    Rejected: 토요일 아침 / 호랑이와 곶감 (not in the legacy project); porting
    all 10 passages (#7-#19 contain ungrammatical LLM output). Reason: cleanest
    text; all 12 flagged_vocab words come from these two.
24. **New episode series value `legacy`.** Rejected: reuse `primer`.
    Reason: keeps ported content distinguishable from generated content.
25. **Token classification:** VX (auxiliaries), VCP (copula), XSN, J*, E*
    and short negation 안/못 before a predicate are grammar tokens. VCN
    (아니다), NNB (것, 수, 때) and MM are content. Rejected: legacy's merged
    lexemes like "안 되다" / "-지 않다". Reason: lexemes stay pure (lemma, pos).
26. **Analyzer lemma rules:** compound nouns merge (애견용품), 님 attaches
    (부모님), XPN attaches (대학교), noun/XR + 하 -> derived VV/VA, noun + 드리
    -> -드리다 VV, and 있다 is always VA. Rejected: trusting raw Kiwi output.
    Reason: Kiwi over-splits and tags 있다 inconsistently, which would create
    duplicate lexemes.
27. **Coverage counts running content tokens (not unique types).**
    Rejected: legacy's type-based ratio. Reason: SPEC 7 and reading
    research measure running words.
28. **Legacy vocab exported to `content/seed/legacy_vocab.json`, not imported
    yet.** Legacy LLM glosses dropped; krdict fills glosses on import.
    Rejected: import now. Reason: no DB until Stage 3; placement (Stage 4)
    may override states.
29. **`web/` scaffold deferred to Stage 3.** Rejected: installing Node in
    Stage 2. Reason: Node not installed and no UI work this stage.
30. **krdict glosses picked by POS match, then easiest grade, then lowest
    sup_no.** Hanja comes from `origin` (CJK characters only).

## 2026-10-03 (Stage 3, Claude Code)

31. **O1 resolved: `tailscale cert`** for `arka18-desktop.tail91f88.ts.net`;
    uvicorn serves TLS on :8443 from `C:\ProgramData\korean-reader\certs\`.
    Renewed every 4 weeks by a SYSTEM scheduled task (`renew_cert.ps1`).
    Rejected: `tailscale serve` (changes the URL/port, another moving part);
    home-CA cert (iPhone profile + trust toggle). Reason: publicly trusted,
    nothing to install on the phone.
32. **O4 resolved: native Windows service via NSSM** (`install_service.ps1`),
    running `server\.venv\Scripts\python.exe scripts\serve.py` as
    LocalSystem; firewall allows :8443 from `100.64.0.0/10` only.
    Rejected: WSL + systemd, Docker. Reason: no extra runtime; the analyzer
    and DB already run natively.
33. **Parchment theme built from scratch** (Gowun Batang body, Nanum Myeongjo
    titles, dark "lamp-lit" variant via `prefers-color-scheme`).
    Rejected: porting legacy `static/index.html` (GitHub-dark, not the
    intended look). Reason: `korean_graded_readers.jsx` was never copied into
    `legacy/`.
34. **Fonts self-hosted via @fontsource**, cached at runtime by the service
    worker (CacheFirst), not precached. Rejected: Google Fonts (offline
    breaks); precaching all ~700 unicode-range slices (~29 MB). Reason: only
    slices actually rendered get cached.
35. **Schema additions to DATA_MODEL:** `episode.updated_at`,
    `lexeme_state.updated_at`, `grammar_state.updated_at` (sync cursor),
    `event.received_at`, `episode.source`, `question.idx`;
    `grammar_point.ja_parallel` nullable until SYLLABUS_MAP;
    `lexeme.gloss_source = none` when krdict has no entry (retried on
    re-ingest). Rejected: separate sync-version table. Reason: single user,
    timestamps suffice.
36. **Paragraph token JSON:** `{s, e, lex}` for content, `{s, e, g}` for coded
    grammar; uncoded grammar morphemes are not stored. The client widens a
    content token's tap target over trailing endings up to the next content
    token or word boundary (키우고 -> 키우다).
37. **API under `/api`, web served same-origin by FastAPI** (SPA fallback).
    Rejected: separate static host + CORS. Reason: one process, one cert.
38. **Sync protocol:** client pushes queued events (`POST /api/events/batch`,
    insert-or-ignore on UUID, returns accepted + duplicate ids, client deletes
    both), then pulls `GET /api/sync/pull?since=<server_time>` (full episode
    payloads + lexeme states). Single-flight on the client.
39. **"Sounds off" flags a sentence from the word popover** (sentence around
    the tapped word). Rejected: per-paragraph flag button. Reason: SPEC 8 is
    per sentence and it keeps the reading page uncluttered.
40. **Ingest without `--publish` keeps an episode's current status.**
    Reason: a re-ingest to refresh glosses must not unpublish.
41. **krdict client throttles live requests (0.5 s) and retries with
    backoff.** Reason: a burst during the first ingest got this machine's IP
    timed out by krdict.

42. **Glosses from a local copy of the krdict dump** (2019 LMF XML export,
    50,031 word entries, mirror github.com/spellcheck-ko/korean-dict-nikl-krdict),
    indexed into `server/data/krdict_local.sqlite` by
    `scripts/build_krdict_local.py`. Lookup order: local dump -> cached API
    responses -> live API (`--live` only). Same target_codes and POS labels
    as the API, so DECISIONS 30's picking rule is unchanged. License:
    CC BY-SA 2.0 KR, (c) 국립국어원; dictionary data is not redistributed
    from this repo (data/ is gitignored). Rejected: live API only (krdict was
    unreachable for hours on 2026-10-03); Wiktionary (no Japanese); stdict
    (Korean-only definitions); LLM glosses (SPEC 5). Reason: same data,
    no runtime dependency on krdict.korean.go.kr.
43. **Stage 4 inputs (chosen by Austin before planning):** the HTSK 1-28
    grammar-point list is drafted by Claude as SYLLABUS_MAP rows (map only,
    no HTSK text) and reviewed by Austin before test sentences are written;
    vocab yes/no bands come from the NIKL learner vocabulary list (A/B/C);
    calibration passages are written by Claude in-session. Rejected: a
    design session first; krdict 초급/중급/고급 levels; corpus frequency
    lists; Austin-supplied passages.

## 2026-10-03 (Stage 4, Claude Code)

44. **HTSK 1-28 = 54 grammar points / 52 checks** (`content/seed/grammar_points.json`,
    mirrored in SYLLABUS_MAP), approved by Austin with the Stage 4 plan.
    Left out: 이래로/이내, 들, L15 compound verbs. Rejected: one check per
    lesson. Reason: lessons bundle unrelated points (e.g. L12 has five particles).
45. **NIKL list = official korean.go.kr .txt** (cp949 TSV, 5,965 rows),
    downloaded to `server/data/` (gitignored, not redistributed). POS map
    명->NNG, 동->VV, 형->VA, 부->MAG, 대->NP, 수->NR, 관->MM, 의->NNB, 감->IC,
    고->NNP; 보 (auxiliaries) and 불 (contractions) skipped. 있다 -> VA. A noun/adverb
    homograph also gets Kiwi's tag as a second key (결국, 안, 한참 appear as NNG
    or MAG in running text). Derived forms the analyzer splits (가능성, 경제적) keep
    their own key and never match tokens. Imported as 5,712 lexemes with
    freq_rank/freq_band. Rejected: keying by lemmatize() alone (Kiwi misreads
    bare forms: 가요 -> 가다).
46. **Vocab test: 96 real words (16 x 6 rank quantiles, seed 20261003) + 24
    Claude-written pseudowords**, validated as absent from NIKL and the local
    krdict index. Only words that surface as themselves in text are sampled.
47. **Placement model: P(known) = sigmoid(a + b(log rank - log 1000)),
    penalised MAP on a grid** (prior N(0, 3^2)), with guessing correction
    P(yes|real) = p + (1-p)fa (fa = Laplace-smoothed pseudoword yes rate) and
    calibration taps as direct observations. Lexemes outside the list rank at
    1.5 x the list's max rank. Rejected: per-band rates only (no smooth
    rank edge); IRT with per-word difficulty (too few answers).
48. **Known threshold 0.6, not 0.5.** In 60 simulated learners 0.5
    under-counted unknown tokens by 3.6 pp (many words sit just above 0.5);
    0.6 was within +1 pp.
49. **States written by placement:** direct evidence first (calibration
    untapped -> known, tapped -> `seen`; yes/no "yes" -> known if the
    guessing-corrected posterior >= threshold), then the model for every ranked
    lexeme; grammar 2/2 -> solid, 1/2 -> practicing, 0/2 -> new (Austin).
    Rows with another source (the manual flagged vocab) are never touched; a
    re-fit replays the latest attempt with a `done` event and resets dropped
    placement rows to `new` (rows are never deleted, so sync can carry it).
50. **Stage 4 acceptance changed (Austin): observed tap rate inside the
    leave-one-out 95% predictive interval for each passage**, instead of
    +/- 2 pp. Reason: with ~70 tokens per passage, a perfectly specified
    simulated learner met +/- 2 pp only 21-36% of the time per passage
    (65% pooled). The interval includes posterior uncertainty in (a, b);
    simulated coverage is 93-95% per passage (80-88% for all three at once).
51. **Placement API + flow:** `GET /api/placement` (items without the
    real/pseudo flag), `POST /api/placement/fit` (fit + states + episode
    coverage refresh, returns the summary). Calibration passages are episodes
    with series `placement`, read in the normal reader in a placement mode
    (no English, no questions). Progress lives in Dexie `meta`, with Undo.
    Rejected: new placement tables. Reason: DECISIONS 8 (derive from the log).
52. **`legacy_vocab.json` still not imported.** Its rows are lookups from the
    legacy app (하다 looked up 17x), not evidence of knowledge; placement
    supersedes it.

53. **Stage 4 closed with its acceptance not met (Austin, 2026-10-04).**
    Placement ran on the iPhone over one evening: states written (419 known,
    79 seen; grammar 31 solid / 17 practicing / 6 new). Time: about 40 min
    of answering (grammar median 15 s per card vs 6 s planned). Wall clock is
    meaningless because it was spread across hours. Calibration: 2 of 3
    passages outside the interval. Austin's vocabulary comes from a textbook
    and drama/podcast exposure, not frequency order, so a rank model only
    partly predicts it (taps AUC 0.78 for log rank, 0.72 for krdict grade).
    The yes/no test ran far more conservative than reading (bare dictionary
    forms like 같다 marked unknown). Accepted anyway: tested words are exact,
    and untested-word guesses get corrected by reading (Stage 6). For any
    redo, shrink to 1 grammar sentence per point and ~60 vocab words.
    Rejected: a hit-rate parameter (no LOO gain), a passages-only fit (still
    2 misses), krdict grade as a covariate (no better than rank).
54. **Stage 5 adds a popover "알아요" (mark known, `set_state` -> manual
    known) and an un-tap for mistaps.** Reason: Austin's vocabulary is
    non-frequency-shaped, so the app will often treat known words as new;
    one tap should fix that rather than waiting for Stage 6 promotion.

## 2026-10-04 (Stage 5, Claude Code)

55. **Stage 5 run overnight with Austin's up-front answers:** proceed on the
    plan without plan-mode approval; publish passing episodes live and deploy;
    Kiwi patterns only for the batch's target points; "due" = `learning` +
    `seen` until FSRS (Stage 6). Rejected: plan only; drafts unpublished; a
    Claude self-count for grammar; skipping due words.
56. **`set_state` is applied on event receipt** (`app/events.py`), source
    `manual`, idempotent and replayable (`replay_manual_states`). The undo of
    "알아요" sends `set_state` with the previous state (still source `manual`,
    so a placement re-fit leaves it alone). Rejected: waiting for a derivation
    job (DECISIONS 54 wants an immediate fix); storing prior source server-side
    (the log must stay client-authored).
57. **Mistap = new event `word_untap`** (same payload as `word_tap`); the tap
    stays in the log. "알아요" also un-taps the word (knowing it means the tap
    wasn't a lookup). Placement mode shows only the mistap button. Rejected:
    deleting the queued `word_tap` (events are append-only).
58. **Story-bible names live in `content/seed/proper_nouns.json`**: Kiwi user
    words (NNP) so 서윤아 / 이선 stay whole, known for coverage (SPEC 7), glossed
    `manual` ("Ethan (name)"). Rejected: parsing names out of STORY_BIBLE.md.
59. **Coverage uses tag aliases for the known set only** (`coverage.known_aliases`):
    -하다 predicates VV<->VA, 아니다 VA<->VCN, MAG/MAJ/IC, NNG<->NNP. Lexemes stay
    keyed by (lemma, pos). Reason: the NIKL list and Kiwi disagree on tags
    (감사하다 is VA in the list, VV from 감사합니다; 아니다 is 형 in the list),
    which made known words count as unknown.
60. **Generator targets 95-98% against the DB as it is**, even though placement
    under-counts Austin's vocabulary (응, 괜찮다, 언니, 알다 count unknown). Episodes
    are therefore simpler than his real level until 알아요 taps catch up.
    Rejected: an "assumed known" list for generation (contradicts placement,
    hides the gap); generating at the real level (fails the stage criterion).
61. **Batch targets (one per episode, all `practicing`):** S01E001 G.HAMNIDA,
    E002 G.HUMBLE_PRON, E003 G.BODA, E004 G.DEON, E005 G.JI_MOTHADA. The arc's
    `new` points (동안, 에 대해, -아/어지다, 위해) wait for lesson cards
    (Stage 8). Every unknown word counts toward the 3-6 "new words",
    including earlier-batch new words still without a state.
62. **The draft checker analyzes paragraph by paragraph**, exactly like ingest.
    Kiwi's reading depends on context (어머니 came out NNP in the joined text).

63. **Library = "up next" card + sections (Austin, 2026-10-04):** seasons
    (S01E### numbered lists, titles from STORY_BIBLE), side stories, then a
    collapsed "연습 · Practice" (legacy/primer). Read episodes stay in place,
    dimmed with a check. "Up next" = first unread season episode, then side
    stories; never practice. Rejected: tabs per series; collapsible full cards;
    folding read episodes into a "Read" group.
64. **Popover buttons in English:** "I know this word" / "✓ Marked known ·
    Undo" / "Tapped by mistake" (Austin found 알아요 / 잘못 눌렀어요 unclear).
    Story text stays Korean.

65. **Known-word tint in the reader (Austin):** known words get a faint
    background tint, unknown words stay plain; on by default, "Highlight known"
    toggle in the reader header (per device). Off in placement mode. The server
    flags `counts_known` on episode lexemes (story names, and words known under
    another tag) so the tint matches coverage. Rejected: underlining unknown
    words instead (Austin chose the tint); both at once.
66. **"I forgot this" (Austin):** a known word's popover offers "✓ Known · I
    forgot this" -> `set_state` learning (unknown for coverage, due again for the
    generator); undo within the visit. Names / alias-known words show "✓ Known"
    with no action. Rejected: setting it back to `new` (loses that it was known
    once; `learning` is what the due list and Stage 6 want).

67. **Stage 5 accepted (Austin, 2026-10-04): naturalness 4/5 or better** on the
    S01E001-005 batch.
68. **Word sets for confirming known vocabulary (Austin; side load of Stage 5):**
    21 Claude-authored themed sets in `content/seed/word_sets.json` (numbers,
    days, months, food, verbs, ...; general categories, not HTSK lists), plus a
    frequency walk over the NIKL list (unmarked words, 40 per page, online only).
    Checklist grid on the phone; checking sends `set_state` known, unchecking a
    known word sends learning (DECISIONS 66), untouched words change nothing.
    Events carry `word_set` instead of `episode_id`. Rejected: card-by-card
    (slower); queueing unmarked words as learning; themed sets only.
69. **Word-set items resolve to analyzer keys:** default `lemmatize(ko)`;
    explicit `keys` where running text splits or merges differently (일월 ->
    일/NR + 월/NNB, so months also carry 월/NNB; 오래되다 -> 오래/MAG + 되다/VV). An
    item is known only when all its keys are. Tests check items in carrier
    sentences. Rejected: surface-form matching (DECISIONS 3).

70. **Read marks sync across devices (Austin, 2026-10-05):** `GET /api/sync/pull`
    returns `completed` (first `episode_complete` per episode, from any device),
    always in full; the client adds marks it doesn't have and keeps its own
    times. Rejected: incremental by cursor (devices that synced before this
    shipped would never get earlier finishes); a progress table (DECISIONS 8:
    derive from the log).

71. **One speaker per paragraph (Austin, 2026-10-05):** dialogue lines are
    `화자: 대사` without quote marks, one speaker per paragraph; narration in its
    own paragraphs. S01E001-002 re-split (text unchanged, except the flagged
    line). The reader styles the speaker label, tightens spacing, and moves the
    English toggle inline ("EN" at the end of the line). Rejected: keeping mixed
    paragraphs; a single global English toggle.
72. **S01E003-005 regenerated with the expanded known set (Austin):** same arc
    beats and targets (G.BODA, G.DEON, G.JI_MOTHADA) since they replace their
    own episodes; Austin had read only E001-002. Second-pass review fixes
    applied (E003 envelope logic, E004 아이였을 때 for 작을 때, E005 line order);
    declined: adding 동안 (still `new`, DECISIONS 61). Canon log entries
    replaced; the wedding is now fixed as next month. The flagged E001 line
    became 어머니: 긴장은 무슨. 밥만 잘 먹었으면서. The generation context drops
    flags whose sentence is no longer in the episode.

73. **Speaker colors (Austin, 2026-10-05):** each character's name has a fixed
    color across episodes (`web/src/speakers.ts`, tokens `--spk-1..8` in
    styles.css with light and dark variants): 이선 blue, 서윤 rose, 어머니/엄마
    amber, 아버지/아빠 green, 준수 purple, 서현 teal, 마이클 slate, 할머니 gold;
    other labels (e.g. 이메일) neutral. Rejected: one accent color for all
    speakers (hard to follow who is talking); colors hashed from the name
    (would not be stable or tuned for contrast).

74. **Dialogue vs narration layout (Austin, 2026-10-05):** dialogue lines get a
    hanging indent (wrapped lines indent under the text; the English translation
    indents to match); narration lines stay flush left with extra space around
    them. Rejected: muting narration's color (narration is already the harder
    text to read).

## 2026-10-05 (Stage 6, Claude Code)

75. **Hidden SRS = full replay from a baseline after every event batch.** Placement and
    the flagged seed write `base_state`/`base_source` (migration 0003); `app.srs.derive`
    resets every lexeme/grammar state row to its baseline and replays the whole log in
    (ts, id) order, writing only rows that change (~40 ms on the live log). py-fsrs with
    no fuzzing, no learning/relearning steps, card_id = lexeme id, reviews at the event's
    client time: state is a pure function of baseline + log. Replaces DECISIONS 56's
    on-receipt `apply_set_state` (set_state is one of the replayed rules, still immediate).
    Rejected: incremental updates (two code paths; replay must equal live); re-running the
    placement fit inside every replay (depends on the lexeme table, slower).
76. **Grading rules (Austin's answers to the Stage 6 questions):** on `episode_complete`
    (not placement series), per distinct content lexeme: tapped -> Again; untapped and due
    -> Good; untapped with no card and not known -> new card as Good (first encounter read
    without a lookup); untapped known / not due -> exposure only. Meaning check wrong ->
    Again, right and untapped -> Good (Easy if <= 8 s). Story names never graded;
    alias-known words count as known. One rating per word per completion.
    Rejected: exposure-only for new words (SPEC 3.2 literal; leaves earlier-batch words
    unknown forever).
77. **Soft lapse instead of a full reset (Austin: Anki lapses made reviews a grind).** A
    tapped known word (and "I forgot this") goes to `learning` with stability <= 3 d and its
    difficulty unchanged (5 if it had no card), so two untapped encounters regraduate it
    (3 -> 11 -> 35 d). "I forgot this" is due at once (last review backdated one stability).
    Rejected: FSRS Again on a known word (difficulty 5 -> 8.3, ~4 encounters to recover);
    ignoring taps on known words.
78. **Graduation at stability >= 21 d:** learning -> known, grammar practicing -> solid.
    Known words keep their card; a later tap soft-lapses them.
79. **Due / counts-known use last_review + stability, not `card.due`.** FSRS stability is
    the time until retrievability falls to 0.9, so SPEC 7's "learning with R >= 0.9" is
    exactly "before last_review + S". py-fsrs rounds intervals up to whole days (>= 1),
    which would have counted a word tapped today as known until tomorrow. Sent to the
    client as `lexeme_states[].due` for the known tint.
80. **Grammar graded only by grammar_check answers** (Austin); presence is an exposure.
    introduced/practicing points start with an unreviewed card; due grammar is listed first
    in `suggested_targets`. Stage 8 drills plug in later.
81. **Due order for the generator:** reviewed cards least retrievable first, then
    never-reviewed cards (placement `seen`, flagged seed, "I forgot") by frequency rank.
    No queue and no backlog: the generator weaves 1-3 per episode from the top; the rest wait.
    Meaning checks: max(1, round(due words woven / 5)) per episode, on due words; ingest
    stores the lexeme id as `target_ref`; the checker prints batch coverage of the top-15 due.
82. **Quick review = 3-option meaning pick (Austin)** on a stored context sentence (ingest
    fills `context_sentence` with the word's span) + TTS; up to 20 items in sync pull,
    sessions of 10, answered items dropped locally; `review_answer` grades only due cards.
    The Library shows a plain "복습" link when items exist -- no counts, badges or totals
    anywhere. Rejected: self-grade reveal (self-report).
83. **Replay inputs travel with events:** `episode_complete.lexeme_ids`, `question_answer.kind
    /target_ref`, `set_state.undo`. Ingest now updates questions in place by idx so ids stay
    stable (re-ingest had been replacing them, which silently dropped old answers from the
    replay). Older events fall back to current episode/question rows.

## OPEN

- ~~O1 HTTPS~~ -> resolved, see 31.
- ~~O4 deploy target~~ -> resolved, see 32.
- ~~O2 Story bible details~~ -> resolved by STORY_BIBLE v3 (2026-10-04).
- **O3 Kanji set for Sino-Korean transparency weighting** -- off until built.
