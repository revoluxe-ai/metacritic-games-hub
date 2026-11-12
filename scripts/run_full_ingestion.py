"""Run a full live ingestion job and print stored game titles."""

from __future__ import annotations

import os

# Ensure no LLM for heuristic verification unless explicitly set
os.environ.setdefault("LLM_API_KEY", "")

from app.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.models import Game, JobStatus
from app.services.ingestion import run_ingestion_job


def main() -> None:
    Base.metadata.create_all(bind=engine)
    limit = int(os.environ.get("GAMES_PER_RUN", "20"))
    db = SessionLocal()
    try:
        before = db.query(Game).count()
        job = run_ingestion_job(db, trigger="manual", limit=limit)
        slugs = (job.details or {}).get("slugs") or []
        titles = []
        for slug in slugs:
            row = db.query(Game).filter(Game.slug == slug).first()
            if row:
                titles.append(row.title)
        after = db.query(Game).count()
        print("job_status", job.status.value)
        print("games_processed", job.games_processed)
        print("games_in_db", after, "(was", before, ")")
        print("message", job.message)
        if job.details:
            print("source", job.details.get("source"))
            print("errors", job.details.get("errors"))
        print("--- titles (this run) ---")
        for i, title in enumerate(titles, 1):
            print(f"{i}. {title}")
        if job.status != JobStatus.success or job.games_processed < limit:
            raise SystemExit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
