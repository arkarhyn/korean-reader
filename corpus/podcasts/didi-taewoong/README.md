# 디디와 정태웅의 한국생활 요모조모 (Didi & Taewoong: Korean Life, Bit by Bit)

Two people (디디 and 정태웅 / 태웅쌤) chat for 23–57 min per episode (~23.6 h total,
~315k Hangul characters) about everyday life in Korea. Source playlist:
https://www.youtube.com/playlist?list=PLekI352WvEBPAgoMY2dl5_5Ml37M9nSLZ

## Layout
- `index.json`: one entry per episode: title, URL, upload date, length,
  subtitle sources, segment and Hangul-character counts, YouTube description.
- `episodes/NN_slug.json`: time-aligned segments
  `{start_ms, end_ms, ko, en?, speaker_change?}`. `NN` is chronological
  (01 = oldest). The show's own ♯ number is `show_no` (it has a duplicate ♯30,
  no ♯16, and episode 16 is an unnumbered special).
- `episodes/NN_slug.md`: the same transcript for reading: timestamp, Korean line,
  English underneath.
- `raw/`: original YouTube subtitle files (json3) that everything is built from.

## Transcript quality
`sources.ko` in each episode says where the Korean came from:
- `manual` (23 episodes): subtitles the creators uploaded themselves. Clean, punctuated, speaker names correct.
- `auto` (10 episodes: 02, 06–09, 11, 12, 14, 21, 22): YouTube auto-captions.
  Expect mishearings (정태웅 → 정태용, 요모조모 → 조모조), no sentence
  boundaries, and `—` / `speaker_change` for turn changes.

English is the creators' manual translation in every episode except 02 (hamburger), which has none.
In auto episodes English cues are matched to the nearest Korean line by time, so
alignment is approximate.

## Stage 7 Phase A: prepared episodes (`prep.py`)
Reader-ready input for the future Listen tab. Nothing here touches the app yet.
- `labels/NN.txt`: one speaker per subtitle cue (`디디` / `태웅` / `둘`, trailing `?` =
  uncertain) and ~4–6 min part breaks with ko/en titles. Written by a Claude Code
  labeling pass that reads the transcript; the Korean itself is never rewritten.
- `prepared/NN_slug.json`: parts → speaker turns → timed lines; `prepared/NN_slug.md` to read.
- `coverage.json`: known-word coverage per clean episode (and per part where
  prepared) against the vocab DB, plus `corpus_top_unknown`: your unknown words
  ranked by how many episodes they appear in.

Done so far: 03, 17, 28 (the three easiest by coverage).

```
python prep.py cues NN                 # -> work/NN.cues.txt for the labeling pass
python prep.py assemble NN             # validates labels/NN.txt, writes prepared/
cd ../../../server; uv run python ../corpus/podcasts/didi-taewoong/prep.py rank [--db SNAPSHOT]
```

Known caveats, found in the sample pass:
- **Per-line English is unreliable, so use turn-level `en`.** Older translations re-flow sentences
  across cues (the English on a cue often belongs to the next Korean cue). Newer
  episodes (bilingual track) align exactly.
- **Some "manual" Korean is itself AI-transcribed.** Episode 03 opens with
  `[AI로 생성된 자막입니다]` and has errors (인청망청 for 흥청망청, 대웅쌤). Even clean
  episodes sometimes misspell 태웅 as 태용.
- **Speaker labels are inferred from content:** about 5–11% of turns are marked `uncertain`,
  mostly rapid back-channel exchanges. Game segments (스무고개 etc.) are very
  fragmented one-word turns.
- **Coverage is about 60–69% per episode and 61–77% per part (Oct 2026, 594 known words).**
  It's slightly understated: `-것 같다` counts 같다, and the 예 / 그 fillers count as words.

## Refresh (new episodes)
`python corpus/podcasts/didi-taewoong/fetch.py`: downloads subtitles for videos
not in `raw/archive.txt` (via `uvx yt-dlp`), then reruns `build.py`.
`python corpus/podcasts/didi-taewoong/build.py` alone rebuilds from `raw/`.
