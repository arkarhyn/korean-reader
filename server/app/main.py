from fastapi import FastAPI

app = FastAPI(title="korean-reader")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
