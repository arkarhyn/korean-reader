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

## Refresh (new episodes)
`python corpus/podcasts/didi-taewoong/fetch.py`: downloads subtitles for videos
not in `raw/archive.txt` (via `uvx yt-dlp`), then reruns `build.py`.
`python corpus/podcasts/didi-taewoong/build.py` alone rebuilds from `raw/`.
