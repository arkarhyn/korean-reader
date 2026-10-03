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

## OPEN

- **O1 HTTPS for the PWA.** iOS requires a secure context for service
  workers (offline mode); plain `http://<ip>` will not work offline.
  Option A (preferred): `tailscale cert` for the desktop's tailnet hostname
  (publicly trusted, no iPhone profile needed).
  Option B: server cert issued from Austin's existing home CA; root installed
  as an iOS profile AND enabled under Settings > General > About >
  Certificate Trust Settings. Decide in Stage 3.
- **O4 Desktop deploy target.** Desktop is always on (confirmed). Need: OS
  (assumed Windows) and run method (WSL + systemd, Docker, or native Windows
  service via NSSM). Decide in Stage 3.
- **O2 Story bible details** (names, city, cast) -- next Project design session.
- **O3 Kanji set for Sino-Korean transparency weighting** -- off until built.
