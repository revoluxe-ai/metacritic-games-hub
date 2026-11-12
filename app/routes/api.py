import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal, get_db
from app.models import JobStatus, WorkerJob, WorkerLog
from app.services.ingestion import run_ingestion_job

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/worker/run-now")
def trigger_worker_run(db: Session = Depends(get_db)) -> dict:
    running = (
        db.query(WorkerJob)
        .filter(WorkerJob.status == JobStatus.running)
        .order_by(WorkerJob.id.desc())
        .first()
    )
    if running:
        return {"ok": False, "message": "A job is already running", "job_id": running.id}

    job = run_ingestion_job(db, trigger="manual")
    return {
        "ok": job.status.value == "success",
        "job_id": job.id,
        "status": job.status.value,
        "message": job.message,
        "games_processed": job.games_processed,
    }


@router.get("/worker/jobs")
def list_jobs(limit: int = 20, db: Session = Depends(get_db)) -> list[dict]:
    jobs = (
        db.query(WorkerJob)
        .order_by(WorkerJob.id.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [
        {
            "id": j.id,
            "status": j.status.value,
            "trigger": j.trigger,
            "started_at": j.started_at.isoformat() if j.started_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            "games_processed": j.games_processed,
            "message": j.message,
        }
        for j in jobs
    ]


@router.get("/worker/events")
async def worker_events() -> StreamingResponse:
    """SSE stream of latest worker job + logs (near real-time)."""

    async def event_generator():
        last_payload = ""
        while True:
            db = SessionLocal()
            try:
                job = (
                    db.query(WorkerJob)
                    .options(joinedload(WorkerJob.logs))
                    .order_by(WorkerJob.id.desc())
                    .first()
                )
                logs = []
                if job:
                    logs = (
                        db.query(WorkerLog)
                        .filter(WorkerLog.job_id == job.id)
                        .order_by(WorkerLog.id.desc())
                        .limit(40)
                        .all()
                    )
                payload = json.dumps(
                    {
                        "ts": datetime.utcnow().isoformat(),
                        "job": None
                        if not job
                        else {
                            "id": job.id,
                            "status": job.status.value,
                            "trigger": job.trigger,
                            "started_at": job.started_at.isoformat(),
                            "finished_at": job.finished_at.isoformat()
                            if job.finished_at
                            else None,
                            "games_processed": job.games_processed,
                            "games_requested": job.games_requested,
                            "message": job.message,
                        },
                        "logs": [
                            {
                                "level": l.level,
                                "message": l.message,
                                "created_at": l.created_at.isoformat(),
                            }
                            for l in reversed(logs)
                        ],
                    }
                )
                if payload != last_payload:
                    last_payload = payload
                    yield f"data: {payload}\n\n"
            finally:
                db.close()
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
