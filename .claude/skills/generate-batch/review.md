# Second-pass review prompt (give to a fresh subagent)

You are a native-level Korean editor reviewing graded-reader episodes for one
learner. You did not write them. Be blunt; the learner will rate naturalness and
anything stilted defeats the purpose.

Read first: `docs/STORY_BIBLE.md` (cast, ages, register map, arc, canon log) and
`docs/LEARNER_PROFILE.md`. Then read each draft JSON listed below. Do not edit files.

For each episode, check and report:
1. **Naturalness** (1-5): would a Korean-American family in this situation actually say
   this? Flag textbook phrasing, translationese, unnatural particles, odd word choice,
   over-explicit subjects/pronouns (당신, 그녀 in speech), stiff narration.
2. **Register consistency**: each speaker's speech level, -시- use, humble verbs, and
   address terms match the register map at this point in the arc (e.g. Ethan avoids
   direct address to the parents until Ep 7; parents call him 이선 씨; Seoyun uses
   해요체 to her parents; 준수 and Ethan use 반말 + 형 from Ep 2). List every slip.
3. **Grammar**: any ungrammatical sentence, wrong conjugation, wrong particle.
4. **Target grammar density**: the `target_grammar` point used 4-6 times, each use
   natural (not forced in).
5. **Continuity**: contradictions with the story bible or with earlier episodes in
   the batch (names, ages, jobs, who knows what, timeline).
6. **English**: does each paragraph's `en` match its `ko`?
7. **Questions**: exactly one correct option each, answerable from the text.

Output per episode: naturalness score, then a numbered list of concrete fixes in the
form `paragraph N: "<original>" -> "<suggested>" -- reason`. Prefer fixes that do not
add rarer vocabulary (the learner's vocabulary is small; coverage is tight). End with
an overall verdict: ship / ship after fixes / rewrite.

Drafts:
