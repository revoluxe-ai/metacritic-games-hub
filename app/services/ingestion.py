"""Hourly ingestion: 20 unprocessed games per run, daily list routing."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import DailyRunState, Game, GamePlatform, JobStatus, WorkerJob, WorkerLog
from app.services.llm import LLMService
from app.services.metacritic import MetacriticClient
from app.services.youtube import fetch_transcript_excerpt, search_lets_play_video_id
from app.services.youtube import lets_play_url


def _log(db: Session, job: WorkerJob, message: str, level: str = "info") -> None:
    db.add(WorkerLog(job_id=job.id, message=message, level=level))
    db.commit()


def get_or_create_daily_state(db: Session, today: date) -> DailyRunState:
    state = db.query(DailyRunState).filter(DailyRunState.run_date == today).first()
    if not state:
        state = DailyRunState(run_date=today, processed_slugs_today=[])
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def _collect_candidates(
    client: MetacriticClient, state: DailyRunState, limit: int
) -> tuple[list[str], str]:
    """Build a slug pool of at least `limit` items (New Releases HTML is often <20)."""
    processed = set(state.processed_slugs_today or [])
    need = limit + len(processed)

    if not state.used_new_releases:
        candidates: list[str] = client.list_new_release_slugs(limit=max(limit * 5, 60))
        source = "new_releases"
        state.used_new_releases = True
        browse_offset = state.browse_offset
        initial_offset = browse_offset
        while len(candidates) < need:
            batch = client.list_browse_slugs(offset=browse_offset, limit=48)
            if not batch:
                break
            browse_offset += len(batch)
            for slug in batch:
                if slug not in candidates:
                    candidates.append(slug)
        state.browse_offset = browse_offset
        if browse_offset > initial_offset:
            source = "new_releases+browse"
        return candidates, source

    candidates = client.list_browse_slugs(offset=state.browse_offset, limit=limit * 3)
    source = f"browse_offset_{state.browse_offset}"
    state.browse_offset += max(len(candidates), limit)
    if len(candidates) < limit:
        extra_offset = state.browse_offset
        while len(candidates) < need:
            batch = client.list_browse_slugs(offset=extra_offset, limit=48)
            if not batch:
                break
            extra_offset += len(batch)
            for slug in batch:
                if slug not in candidates:
                    candidates.append(slug)
        state.browse_offset = extra_offset
    return candidates, source


def pick_slugs_for_run(db: Session, client: MetacriticClient, limit: int) -> tuple[list[str], str]:
    today = date.today()
    state = get_or_create_daily_state(db, today)
    processed = set(state.processed_slugs_today or [])

    candidates, source = _collect_candidates(client, state, limit)

    picked: list[str] = []
    for slug in candidates:
        if slug in processed:
            continue
        picked.append(slug)
        if len(picked) >= limit:
            break

    db.add(state)
    db.commit()
    return picked, source


def upsert_game(db: Session, payload, llm: LLMService, enable_youtube: bool = True) -> Game:
    game = db.query(Game).filter(Game.slug == payload.slug).first()
    if not game:
        game = Game(slug=payload.slug, title=payload.title)
        db.add(game)

    game.title = payload.title
    game.developer = payload.developer
    game.description = payload.description
    game.cover_url = payload.cover_url
    game.trailer_url = payload.trailer_url
    game.metacritic_url = payload.metacritic_url
    game.release_date = payload.release_date
    game.genres = payload.genres
    game.last_processed_at = datetime.utcnow()
    game.description_embedding_text = " ".join(
        filter(
            None,
            [
                payload.description or "",
                " ".join(payload.genres),
                game.critic_summary or "",
                game.user_summary or "",
            ],
        )
    )[:4000]

    game.critic_summary = llm.summarize_reviews(payload, critic=True)
    game.user_summary = llm.summarize_reviews(payload, critic=False)

    settings = get_settings()
    if enable_youtube and settings.youtube_enabled:
        vid = search_lets_play_video_id(payload.title)
        if vid:
            excerpt = fetch_transcript_excerpt(vid)
            if excerpt:
                takeaway = llm.youtube_takeaway(payload.title, excerpt)
                game.youtube_takeaway = f"{takeaway}\n\nSource: {lets_play_url(vid)}"

    db.flush()
    db.query(GamePlatform).filter(GamePlatform.game_id == game.id).delete()
    for p in payload.platforms:
        db.add(
            GamePlatform(
                game_id=game.id,
                platform_name=p.name,
                platform_slug=p.slug,
                metascore=p.metascore,
                user_score=p.user_score,
                is_lead=p.is_lead,
            )
        )

    db.commit()
    db.refresh(game)
    return game


def run_ingestion_job(
    db: Session,
    trigger: str = "scheduled",
    limit: int | None = None,
) -> WorkerJob:
    settings = get_settings()
    limit = limit or settings.games_per_run

    job = WorkerJob(
        status=JobStatus.running,
        trigger=trigger,
        games_requested=limit,
        started_at=datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    if not settings.scraper_enabled:
        job.status = JobStatus.failed
        job.message = "SCRAPER_ENABLED=false"
        job.finished_at = datetime.utcnow()
        db.commit()
        _log(db, job, "Scraper disabled by configuration", "error")
        return job

    processed_slugs: list[str] = []
    errors: list[str] = []
    source = "unknown"

    try:
        with MetacriticClient() as client:
            slugs, source = pick_slugs_for_run(db, client, limit)
            _log(db, job, f"Source={source}, candidate slugs={len(slugs)}")

            llm = LLMService()
            for slug in slugs:
                try:
                    payload = client.enrich_game(slug)
                    upsert_game(db, payload, llm, enable_youtube=True)
                    processed_slugs.append(slug)
                    _log(db, job, f"OK {slug} — {payload.title}")
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{slug}: {exc}")
                    _log(db, job, f"FAIL {slug}: {exc}", "error")

            today = date.today()
            state = get_or_create_daily_state(db, today)
            all_processed = list(state.processed_slugs_today or [])
            all_processed.extend(processed_slugs)
            state.processed_slugs_today = list(dict.fromkeys(all_processed))
            db.add(state)
            db.commit()

        job.games_processed = len(processed_slugs)
        job.details = {"slugs": processed_slugs, "errors": errors, "source": source}
        job.status = JobStatus.success if processed_slugs else JobStatus.failed
        job.message = (
            f"Processed {len(processed_slugs)}/{limit} games"
            if processed_slugs
            else "No games processed"
        )
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.failed
        job.message = str(exc)
        _log(db, job, f"Job failed: {exc}", "error")

    job.finished_at = datetime.utcnow()
    db.commit()
    db.refresh(job)
    return job
