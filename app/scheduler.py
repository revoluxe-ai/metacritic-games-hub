"""Embedded APScheduler for single-process deploys (e.g. Railway)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings
from app.database import SessionLocal
from app.services.ingestion import run_ingestion_job

log = logging.getLogger("scheduler")
_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.run_scheduler:
        log.info("RUN_SCHEDULER is false — hourly job disabled")
        return None
    if _scheduler is not None:
        return _scheduler

    def _job() -> None:
        db = SessionLocal()
        try:
            run_ingestion_job(db, trigger="scheduled")
        finally:
            db.close()

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        _job,
        IntervalTrigger(minutes=settings.scheduler_interval_minutes),
        id="metacritic_ingestion",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    log.info(
        "Scheduler started (every %s minutes)",
        settings.scheduler_interval_minutes,
    )

    if settings.run_ingestion_on_startup and settings.scraper_enabled:
        log.info("RUN_INGESTION_ON_STARTUP=true — running initial ingestion")
        _job()

    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("Scheduler shut down")
