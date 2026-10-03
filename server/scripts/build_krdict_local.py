"""Download the 한국어기초사전 dump (CC BY-SA 2.0 KR) and build data/krdict_local.sqlite.

    uv run python scripts/build_krdict_local.py [--skip-download]

XML files (~390 MB) go to data/krdict_dump/ (gitignored); re-runs skip files
already downloaded.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from app.config import KRDICT_DUMP_DIR, KRDICT_LOCAL_PATH  # noqa: E402
from app.krdict.local import build  # noqa: E402

MIRROR = "https://raw.githubusercontent.com/spellcheck-ko/korean-dict-nikl-krdict/master/"
FILES = [f"{n}.xml" for n in range(5000, 50001, 5000)] + ["51947.xml"]


def download() -> None:
    KRDICT_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True) as http:
        for name in FILES:
            out = KRDICT_DUMP_DIR / name
            if out.is_file() and out.stat().st_size > 0:
                continue
            print(f"downloading {name}", flush=True)
            tmp = out.with_suffix(".part")
            with http.stream("GET", MIRROR + name) as r, tmp.open("wb") as f:
                r.raise_for_status()
                for chunk in r.iter_bytes():
                    f.write(chunk)
            tmp.replace(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-download", action="store_true")
    args = ap.parse_args()
    if not args.skip_download:
        download()
    n = build(KRDICT_LOCAL_PATH, [KRDICT_DUMP_DIR / name for name in FILES])
    print(f"{n} word entries -> {KRDICT_LOCAL_PATH}")


if __name__ == "__main__":
    main()
