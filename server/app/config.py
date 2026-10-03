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

# Relative paths in .env resolve against server/.
def _server_path(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else SERVER_ROOT / p


DATABASE_PATH = _server_path(os.getenv("DATABASE_PATH", "data/korean_reader.db"))
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8443"))
TLS_CERT_PATH = os.getenv("TLS_CERT_PATH", "")
TLS_KEY_PATH = os.getenv("TLS_KEY_PATH", "")
WEB_DIST = REPO_ROOT / "web" / "dist"
