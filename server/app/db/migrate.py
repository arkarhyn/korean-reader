from alembic import command
from alembic.config import Config
from sqlalchemy import Engine

from ..config import SERVER_ROOT


def upgrade(engine: Engine, revision: str = "head") -> None:
    """Run Alembic migrations against `engine` (serve.py and tests)."""
    cfg = Config(str(SERVER_ROOT / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, revision)
