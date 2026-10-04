"""Download the NIKL 한국어 학습용 어휘 목록 (2003) to data/nikl_vocab.txt (gitignored).

    uv run python scripts/fetch_nikl_vocab.py

Official file from korean.go.kr (etc_seq=70): cp949 TSV, 순위 단어 품사 풀이 등급.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.config import NIKL_VOCAB_PATH  # noqa: E402

URL = ("https://www.korean.go.kr/common/download.do?file_path=etcData"
       "&c_file_name=b73a8438-4713-4436-8481-ec26fd0dce2a_0.txt&o_file_name=nikl_vocab.txt")


def main() -> None:
    r = httpx.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60, follow_redirects=True)
    r.raise_for_status()
    if not r.content.decode("cp949").startswith("순위"):
        sys.exit("unexpected file content (expected a cp949 TSV starting with 순위)")
    NIKL_VOCAB_PATH.parent.mkdir(parents=True, exist_ok=True)
    NIKL_VOCAB_PATH.write_bytes(r.content)
    print(f"wrote {NIKL_VOCAB_PATH} ({len(r.content):,} bytes)")


if __name__ == "__main__":
    main()
