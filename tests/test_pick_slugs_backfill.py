"""pick_slugs_for_run retries games that were saved without platform rows."""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import DailyRunState, Game, GamePlatform
from app.services.ingestion import pick_slugs_for_run, slugs_missing_platforms


class _FakeClient:
    def list_new_release_slugs(self, limit: int = 20) -> list[str]:
        return ["brand-new-game", "another-new-game"]

    def list_browse_slugs(self, offset: int = 0, limit: int = 48) -> list[str]:
        return ["browse-game"] if offset <= 48 else []


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_slugs_missing_platforms_skips_games_that_already_have_rows():
    db = _session()
    incomplete = Game(slug="no-plats", title="No Plats", metacritic_url="https://www.metacritic.com/game/no-plats/")
    complete = Game(slug="has-plats", title="Has Plats", metacritic_url="https://www.metacritic.com/game/has-plats/")
    db.add_all([incomplete, complete])
    db.flush()
    db.add(
        GamePlatform(
            game_id=complete.id,
            platform_name="PC",
            platform_slug="pc",
            metascore=80,
            user_score=7.5,
            is_lead=True,
        )
    )
    db.commit()
    assert slugs_missing_platforms(db, 10) == ["no-plats"]


def test_pick_slugs_backfills_incomplete_games_before_new_releases():
    db = _session()
    db.add(Game(slug="needs-scores", title="Needs Scores", metacritic_url="https://www.metacritic.com/game/needs-scores/"))
    db.add(
        DailyRunState(
            run_date=date.today(),
            used_new_releases=True,
            browse_offset=48,
            processed_slugs_today=["already-ok"],
        )
    )
    db.commit()

    picked, source = pick_slugs_for_run(db, _FakeClient(), limit=2)
    assert picked[0] == "needs-scores"
    assert "backfill_missing_platforms" in source
    # Remaining slot can come from the browse/new-release pool.
    assert len(picked) == 2
    assert "needs-scores" in picked
