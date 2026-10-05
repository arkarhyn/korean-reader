---
name: generate-batch
description: Generate the next batch of graded-reader episodes for korean-reader (SPEC 5) -- fetch generation context, draft episode JSON, coverage swap loop, second-pass review, ingest. Use when Austin asks to generate episodes / a batch / the next episodes.
---

# /generate-batch [N=5]

Generates N episodes of the main series (or a side series if asked) and loads
them into the DB. All commands run from `server/`. Never call any paid API.

## 1. Context
```
uv run python scripts/export_context.py            # -> content/generation-context.json
```
Read the JSON plus `docs/STORY_BIBLE.md` (arc table, cast, register map, canon log)
and `docs/LEARNER_PROFILE.md`. Key fields:
- `next_episode_id`, `targets` (coverage 95-98%, 3-6 new words, target grammar 4-6x, 400-700 hangul)
- `known` (lemma/POS strings), `proper_nouns` (count as known; add new canon names to
  `content/seed/proper_nouns.json` BEFORE checking)
- `due` (hidden SRS, Stage 6): FSRS-due words in priority order -- reviewed words least
  likely remembered first (`retrievability`), then never-reviewed ones (`reviewed: false`)
  by frequency. Weave 1-3 per episode, working down from the top of the list across the
  batch (prefer ones that fit the scene); a due word counts as unknown for coverage
- `suggested_targets` lists due grammar first
- `new_word_candidates` (frequent, unknown, glossed): pick most new words from here or
  from what the scene truly needs (e.g. 결혼식)
- `suggested_targets` (practicing points with a pattern, not recently targeted) and
  `grammar_avoid` (state `new`: do not use unless it is the episode's target)
- `recent_episodes` (summaries for continuity), `flagged_sentences` ("sounds off" taps:
  rewrite or avoid those constructions; mention in the batch report)
- `primer_requests` (Stage 7): podcast parts Austin tapped "프라이머 만들기" on, each with its
  top unknown `words`. Draft one primer per request in addition to the batch (section 2b).

Pick one target per episode from `suggested_targets`, guided by the arc table's focus.
A target must have a `kiwi_pattern` in `content/seed/grammar_points.json`; add one
(plus a test in `server/tests/test_generation.py`) if the arc needs a new point.

## 2. Draft
Write `content/episodes/s01/S01E00N.json` (format: `server/app/content/schema.py`):
`id, series: "main", title_ko, title_en, register_tags, target_grammar, summary`
(one line, used as continuity in later batches), `paragraphs [{ko, en}]`, `questions`.

Writing rules:
- Mostly dialogue (LEARNER_PROFILE: narration reads far harder); narration only as
  linking lines.
- **One speaker per paragraph** (Austin, DECISIONS 71): every dialogue line is its own
  paragraph, written `화자: 대사` with no quote marks. Narration gets its own
  paragraphs and never shares one with dialogue. Don't run two speakers together.
- Speech must follow the STORY_BIBLE register map exactly (who uses 반말, 해요체, 합니다체,
  -시-, humble verbs, address terms) at this point in the arc.
- Write natural Korean first, then simplify vocabulary. Never bend grammar to dodge a word;
  swap the word or restructure the line.
- New words: use each at least twice when natural (it is the first exposure).
- Target grammar 4-6 times, in natural spots; don't stack it into one paragraph.
- English `en` per paragraph: faithful, natural translation (it's a reading aid).
- 3-5 questions, tap-only: 2-3 comprehension; meaning checks on **due** words, about 1 per
  5 due words woven in, at least 1 (`target_ref` = the lemma; ingest stores the lexeme id;
  answers grade the word's SRS card); optionally 1 grammar_check (`target_ref` = code; this
  is the only thing that grades grammar). Options short, one clearly right answer.
- At most one Japanese-parallel moment per episode, correct about where it breaks.

## 2b. Primers (only if `primer_requests` is non-empty)
A primer pre-teaches a podcast part's words before Austin listens (DECISIONS 87). Write
`content/episodes/primer/<part id>.json`: `id: "primer-<part id>"`, `series: "primer"`,
`source` = the request's `source` (`primer:<part id>`; this links it to the part in the
Listen tab), `target_grammar` optional (null is fine), titles naming the topic.
- Pick 5-10 of the request's `words` that fit one everyday scene on the part's topic
  (`title_ko` / `title_en`); use each 2-3 times in clearly guessable context.
- Characters from the S01 cast or a neutral everyday scene; same register and one-speaker-
  per-paragraph rules as episodes. Original text: never quote or paraphrase the podcast.
- Same coverage band and length; the checker allows 5-10 new words for `primer` and no
  target grammar. 2-3 questions, including meaning checks on 1-2 primer words.

## 3. Coverage swap loop
```
uv run python scripts/coverage_check.py ../content/episodes/s01/S01E00N.json
```
Run it on all drafts at once at the end: the `batch:` line shows how many of the top-15
due words the batch uses; cover as many as fit naturally and list the rest in the report.
Fix every `!` problem. For unknown words not meant as new/due, swap to a known synonym
or restructure. Watch for analyzer artifacts (a name split into pieces -> add it to
proper_nouns.json; an odd lemma -> rephrase). Re-run until OK. If a beat cannot reach
the band without becoming unnatural, split it over two episodes (STORY_BIBLE allows it)
or flag it in the report -- never ship unnatural Korean to hit a number.

## 4. Second-pass review
Spawn ONE fresh subagent (general-purpose) with the prompt in `review.md` (in this
skill directory), listing the draft paths. It must not see your drafting reasoning.
Apply its fixes that you agree with, re-run step 3, and note disagreements in the report.

## 5. Ingest + canon
- Append new facts to `docs/STORY_BIBLE.md` "Canon log" (one line per episode:
  `S01E00N: ...` names, places, things said that later episodes must respect).
- Back up the live DB first (sqlite backup API, not a file copy: WAL mode), then
```
uv run python scripts/ingest_episodes.py ../content/episodes/s01/S01E00N.json ... --publish
```
- If web code changed: `cd web; npm run build`, then restart the `korean-reader` service.

## 6. Report
Per episode: id, title, coverage, new words, due words used, target x count, review
notes, flagged sentences addressed; per primer: which part and words it covers.
Update `docs/STATUS.md`.
