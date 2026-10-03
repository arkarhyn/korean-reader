import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_ROOT = REPO_ROOT / "server"
CONTENT_DIR = REPO_ROOT / "content"
DATA_DIR = SERVER_ROOT / "data"
LEGACY_DB = REPO_ROOT / "legacy" / "Graded-Reader-Project" / "data" / "vocab.db"

load_dotenv(REPO_ROOT / ".env")

KRDICT_API_KEY = os.getenv("KRDICT_API_KEY", "")
KRDICT_CACHE_PATH = Path(os.getenv("KRDICT_CACHE_PATH", DATA_DIR / "krdict_cache.sqlite"))
