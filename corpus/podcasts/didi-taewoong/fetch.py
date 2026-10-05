"""Fetch subtitles for any new playlist videos, then rebuild episodes/ and index.json.

Run: `python corpus/podcasts/didi-taewoong/fetch.py`  (needs `uv` on PATH; yt-dlp runs via uvx)
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
PLAYLIST = "https://www.youtube.com/playlist?list=PLekI352WvEBPAgoMY2dl5_5Ml37M9nSLZ"

# Manual ko/en subs when the creators uploaded them; auto "Korean (Original)" as fallback.
# build.py prefers manual ko over ko-orig, and en over en-US.
subprocess.run(
    ["uvx", "yt-dlp", "--skip-download", "--no-warnings",
     "--write-subs", "--write-auto-subs", "--sub-langs", "ko,en,en-US,ko-orig",
     "--sub-format", "json3", "--sleep-subtitles", "2", "--write-info-json",
     "--no-write-playlist-metafiles",
     "--download-archive", os.path.join(RAW, "archive.txt"),
     "-o", os.path.join(RAW, "%(id)s.%(ext)s"), PLAYLIST],
    env={**os.environ, "PYTHONIOENCODING": "utf-8"}, check=False,
)
# Playlist positions shift as new episodes are added at the top; re-read them all
# so `order` stays correct even for already-fetched videos.
order = subprocess.run(
    ["uvx", "yt-dlp", "--flat-playlist", "--no-warnings",
     "--print", "%(playlist_index)s %(id)s", PLAYLIST],
    env={**os.environ, "PYTHONIOENCODING": "utf-8"}, capture_output=True, text=True, check=True,
).stdout
with open(os.path.join(RAW, "playlist.txt"), "w", encoding="utf-8") as f:
    f.write(order)
subprocess.run([sys.executable, os.path.join(HERE, "build.py")], check=True)
for f in glob.glob(os.path.join(RAW, "*.info.json")):
    os.remove(f)  # metadata now lives in index.json; info files are mostly stream URLs
