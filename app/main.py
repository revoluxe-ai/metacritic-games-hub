from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app import models  # noqa: F401 — register models
from app.scheduler import shutdown_scheduler, start_scheduler
from app.routes import api, web


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Metacritic Games Hub", version="1.1.0", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(web.router)
app.include_router(api.router)


@app.get("/health")
def health() -> dict:
    from app.config import get_settings

    settings = get_settings()
    return {
        "status": "ok",
        "scheduler": settings.run_scheduler,
        "database": settings.database_url.split("@")[-1][:40],
    }
