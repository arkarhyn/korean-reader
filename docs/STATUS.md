# STATUS

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
