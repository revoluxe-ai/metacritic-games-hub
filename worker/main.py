"""Background worker: APScheduler hourly ingestion + graceful shutdown."""

from __future__ import annotations

import logging
import signal
import sys
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import SessionLocal, engine
from app.database import Base
from app.services.ingestion import run_ingestion_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("worker")


def scheduled_job() -> None:
    db = SessionLocal()
    try:
        run_ingestion_job(db, trigger="scheduled")
    finally:
        db.close()


def main() -> None:
    settings = get_settings()
    Base.metadata.create_all(bind=engine)

    scheduler = BlockingScheduler()
    scheduler.add_job(
        scheduled_job,
        IntervalTrigger(minutes=settings.scheduler_interval_minutes),
        id="metacritic_ingestion",
        max_instances=1,
        coalesce=True,
    )

    def shutdown(signum: int, frame: object) -> None:
        log.info("Shutdown signal %s", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # First run shortly after startup (unless disabled)
    if settings.scraper_enabled:
        log.info("Running initial ingestion on worker startup")
        scheduled_job()

    log.info(
        "Worker started; interval=%s minutes",
        settings.scheduler_interval_minutes,
    )
    scheduler.start()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.exception("Worker crashed")
        time.sleep(5)
        raise
