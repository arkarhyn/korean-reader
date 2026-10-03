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
