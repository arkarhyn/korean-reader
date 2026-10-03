from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .api.routes import router
from .config import WEB_DIST

app = FastAPI(title="korean-reader")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _web_file(path: str) -> Path | None:
    """File under web/dist for `path`, falling back to index.html for client routes."""
    root = WEB_DIST.resolve()
    candidate = (root / path).resolve()
    if path and candidate.is_relative_to(root) and candidate.is_file():
        return candidate
    index = root / "index.html"
    return index if index.is_file() else None


@app.get("/{path:path}", include_in_schema=False)
def web(path: str):
    if path.startswith("api/"):
        raise HTTPException(404)
    f = _web_file(path)
    if f is None:
        raise HTTPException(404, "web/dist not built (cd web; npm run build)")
    # The service worker and shell must revalidate so updates reach the phone.
    no_cache = f.name in {"index.html", "sw.js", "registerSW.js", "manifest.webmanifest"}
    return FileResponse(f, headers={"Cache-Control": "no-cache"} if no_cache else None)
