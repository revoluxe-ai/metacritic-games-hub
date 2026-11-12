"""Verify live Metacritic API access (run in CI or locally)."""

from app.services.metacritic import MetacriticClient


def main() -> None:
    with MetacriticClient() as client:
        slugs = client.list_browse_slugs(offset=0, limit=3)
        print("browse slugs:", slugs)
        new_slugs = client.list_new_release_slugs(limit=5)
        print("new release slugs:", new_slugs[:5])
        if slugs:
            game = client.enrich_game(slugs[0])
            print(
                "enriched:",
                game.title,
                "platforms",
                len(game.platforms),
                "critic reviews",
                len(game.critic_reviews),
            )


if __name__ == "__main__":
    main()
