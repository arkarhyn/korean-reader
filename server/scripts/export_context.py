"""Write the generation context (same JSON as GET /api/export/generation-context).

    uv run python scripts/export_context.py [--out PATH]

Default output: content/generation-context.json (gitignored).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import CONTENT_DIR  # noqa: E402
from app.db import make_engine, make_sessionmaker  # noqa: E402
from app.db.migrate import upgrade  # noqa: E402
from app.generation import build_context  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=CONTENT_DIR / "generation-context.json")
    args = ap.parse_args()
    engine = make_engine()
    upgrade(engine)
    with make_sessionmaker(engine)() as session:
        ctx = build_context(session)
    args.out.write_text(json.dumps(ctx, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {args.out}: next {ctx['next_episode_id']}, {len(ctx['known'])} known, {len(ctx['due'])} due, "
          f"suggested targets {', '.join(ctx['suggested_targets'][:6])}; {len(ctx['flagged_sentences'])} flagged")


if __name__ == "__main__":
    main()
