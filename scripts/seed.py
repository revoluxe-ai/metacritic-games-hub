"""Load sample games so the UI is demonstrable without live scraping."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from app.database import SessionLocal
from app.models import Game, GamePlatform

SAMPLE_PATH = Path(__file__).parent / "sample_games.json"


def seed(if_empty: bool = False) -> int:
    if not SAMPLE_PATH.exists():
        print("No sample_games.json")
        return 0

    data = json.loads(SAMPLE_PATH.read_text())
    db = SessionLocal()
    try:
        existing = db.query(Game).count()
        if if_empty and existing > 0:
            print(f"Skip seed: {existing} games already in DB")
            return 0

        count = 0
        for item in data:
            game = db.query(Game).filter(Game.slug == item["slug"]).first()
            if not game:
                game = Game(slug=item["slug"], title=item["title"])
                db.add(game)

            game.title = item["title"]
            game.developer = item.get("developer")
            game.description = item.get("description")
            game.cover_url = item.get("cover_url")
            game.trailer_url = item.get("trailer_url")
            game.metacritic_url = item.get("metacritic_url")
            game.release_date = item.get("release_date")
            game.genres = item.get("genres", [])
            game.critic_summary = item.get("critic_summary")
            game.user_summary = item.get("user_summary")
            game.youtube_takeaway = item.get("youtube_takeaway")
            game.description_embedding_text = (game.description or "")[:2000]
            game.last_processed_at = datetime.utcnow()

            db.flush()
            db.query(GamePlatform).filter(GamePlatform.game_id == game.id).delete()
            for p in item.get("platforms", []):
                db.add(
                    GamePlatform(
                        game_id=game.id,
                        platform_name=p["name"],
                        platform_slug=p["slug"],
                        metascore=p.get("metascore"),
                        user_score=p.get("user_score"),
                        is_lead=p.get("is_lead", False),
                    )
                )
            count += 1

        db.commit()
        print(f"Seeded/updated {count} games")
        return count
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-empty", action="store_true")
    args = parser.parse_args()
    seed(if_empty=args.if_empty)


if __name__ == "__main__":
    main()
