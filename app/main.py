from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import api, web

app = FastAPI(title="Metacritic Games Hub", version="1.0.0")

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(web.router)
app.include_router(api.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
