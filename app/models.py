from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"


class DailyRunState(Base):
    """Tracks which list/page to use for hourly ingestion each calendar day."""

    __tablename__ = "daily_run_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    used_new_releases: Mapped[bool] = mapped_column(Boolean, default=False)
    browse_offset: Mapped[int] = mapped_column(Integer, default=0)
    processed_slugs_today: Mapped[list] = mapped_column(JSON, default=list)


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    developer: Mapped[str | None] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    cover_url: Mapped[str | None] = mapped_column(String(1024))
    trailer_url: Mapped[str | None] = mapped_column(String(1024))
    metacritic_url: Mapped[str] = mapped_column(String(1024))
    release_date: Mapped[str | None] = mapped_column(String(32))
    genres: Mapped[list] = mapped_column(JSON, default=list)

    critic_summary: Mapped[str | None] = mapped_column(Text)
    user_summary: Mapped[str | None] = mapped_column(Text)
    youtube_takeaway: Mapped[str | None] = mapped_column(Text)

    description_embedding_text: Mapped[str | None] = mapped_column(Text)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_processed_at: Mapped[datetime | None] = mapped_column(DateTime)

    platforms: Mapped[list[GamePlatform]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class GamePlatform(Base):
    __tablename__ = "game_platforms"
    __table_args__ = (
        UniqueConstraint("game_id", "platform_slug", name="uq_game_platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    platform_name: Mapped[str] = mapped_column(String(128))
    platform_slug: Mapped[str] = mapped_column(String(128))
    metascore: Mapped[int | None] = mapped_column(Integer)
    user_score: Mapped[float | None] = mapped_column(Float)
    is_lead: Mapped[bool] = mapped_column(Boolean, default=False)

    game: Mapped[Game] = relationship(back_populates="platforms")


class WorkerJob(Base):
    __tablename__ = "worker_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.pending
    )
    trigger: Mapped[str] = mapped_column(String(32), default="scheduled")
    games_requested: Mapped[int] = mapped_column(Integer, default=0)
    games_processed: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSON)

    logs: Mapped[list[WorkerLog]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class WorkerLog(Base):
    __tablename__ = "worker_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("worker_jobs.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    level: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text)

    job: Mapped[WorkerJob] = relationship(back_populates="logs")
