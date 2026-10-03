"""Run the server: migrate, then uvicorn (TLS when TLS_CERT_PATH/TLS_KEY_PATH are set).

    uv run python scripts/serve.py

Used by the NSSM service (scripts/install_service.ps1).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn  # noqa: E402

from app.config import SERVER_HOST, SERVER_PORT, TLS_CERT_PATH, TLS_KEY_PATH  # noqa: E402
from app.db import make_engine  # noqa: E402
from app.db.migrate import upgrade  # noqa: E402


def main() -> None:
    engine = make_engine()
    upgrade(engine)
    engine.dispose()
    tls = {"ssl_certfile": TLS_CERT_PATH, "ssl_keyfile": TLS_KEY_PATH} if TLS_CERT_PATH and TLS_KEY_PATH else {}
    print(f"serving on {'https' if tls else 'http'}://{SERVER_HOST}:{SERVER_PORT}", flush=True)
    uvicorn.run("app.main:app", host=SERVER_HOST, port=SERVER_PORT, **tls)


if __name__ == "__main__":
    main()
