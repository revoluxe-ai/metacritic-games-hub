"""Metacritic data access via public backend JSON API + HTML list pages."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.config import get_settings

USER_AGENT = (
    "Mozilla/5.0 (compatible; SkytecMetacriticHub/1.0; +https://github.com)"
)


@dataclass
class PlatformScore:
    name: str
    slug: str
    metascore: int | None
    user_score: float | None
    is_lead: bool = False


@dataclass
class ReviewSnippet:
    score: int | float | None
    quote: str
    author: str | None = None


@dataclass
class GamePayload:
    slug: str
    title: str
    developer: str | None
    description: str | None
    cover_url: str | None
    trailer_url: str | None
    metacritic_url: str
    release_date: str | None
    genres: list[str] = field(default_factory=list)
    platforms: list[PlatformScore] = field(default_factory=list)
    critic_reviews: list[ReviewSnippet] = field(default_factory=list)
    user_reviews: list[ReviewSnippet] = field(default_factory=list)


class MetacriticClient:
    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.metacritic_api_key
        self.base = settings.metacritic_base
        self.site = settings.metacritic_site
        self._client = httpx.Client(
            timeout=30.0,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> MetacriticClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> dict:
        q = {"apiKey": self.api_key, **(params or {})}
        url = f"{self.base}{path}"
        resp = self._client.get(url, params=q)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def image_url_from_bucket(bucket_path: str | None) -> str | None:
        if not bucket_path:
            return None
        return f"https://www.metacritic.com/a/img/catalog{bucket_path}"

    def list_new_release_slugs(self, limit: int = 100) -> list[str]:
        """Parse slugs from the New Releases browse page."""
        url = f"{self.site}/browse/game/release-date/new-releases/all/"
        html = self._client.get(url).text
        return parse_new_release_slugs_from_html(html, limit=limit)

    def list_browse_slugs(self, offset: int = 0, limit: int = 24) -> list[str]:
        data = self._get_json(
            "/finder/metacritic/web",
            {
                "sortBy": "-releaseDate",
                "mcoTypeId": 13,
                "offset": offset,
                "limit": limit,
                "componentName": "finder",
                "componentType": "Finder",
            },
        )
        items = data.get("data", {}).get("items", [])
        return [item["slug"] for item in items if item.get("slug")]

    def fetch_product(self, slug: str) -> dict:
        return self._get_json(
            f"/games/metacritic/{slug}/web",
            {"componentName": "product", "componentType": "Product"},
        )

    def fetch_user_stats(self, slug: str, platform_slug: str) -> dict | None:
        try:
            return self._get_json(
                f"/reviews/metacritic/user/games/{slug}/stats/web",
                {
                    "platform": platform_slug,
                    "componentName": "user-score-summary",
                    "componentType": "ScoreSummary",
                },
            )
        except httpx.HTTPError:
            return None

    def fetch_critic_reviews(self, slug: str, limit: int = 15) -> list[ReviewSnippet]:
        data = self._get_json(
            f"/reviews/metacritic/critic/games/{slug}/web",
            {
                "offset": 0,
                "limit": limit,
                "sort": "date",
                "componentName": "latest-critic-reviews",
                "componentType": "CriticReviewList",
            },
        )
        out: list[ReviewSnippet] = []
        for r in data.get("data", {}).get("items", []):
            out.append(
                ReviewSnippet(
                    score=r.get("score"),
                    quote=(r.get("quote") or "").strip(),
                    author=r.get("publicationName"),
                )
            )
        return out

    def fetch_user_reviews(self, slug: str, limit: int = 15) -> list[ReviewSnippet]:
        data = self._get_json(
            f"/reviews/metacritic/user/games/{slug}/web",
            {
                "offset": 0,
                "limit": limit,
                "sort": "date",
                "componentName": "latest-user-reviews",
                "componentType": "UserReviewList",
            },
        )
        out: list[ReviewSnippet] = []
        for r in data.get("data", {}).get("items", []):
            out.append(
                ReviewSnippet(
                    score=r.get("score"),
                    quote=(r.get("quote") or "").strip(),
                    author=r.get("authorName") or r.get("username"),
                )
            )
        return out

    def enrich_game(self, slug: str) -> GamePayload:
        product = self.fetch_product(slug)
        item = product["data"]["item"]
        title = item.get("title") or slug
        description = item.get("description")
        release_date = item.get("releaseDate") or item.get("releaseDateText")

        developer = None
        production = item.get("production") or {}
        for company in production.get("companies") or []:
            if company.get("typeName") == "Developer":
                developer = company.get("name")
                break

        cover_url = None
        for img in item.get("images") or []:
            if img.get("typeName") in ("mainImage", "cardImage"):
                cover_url = self.image_url_from_bucket(img.get("bucketPath"))
                if cover_url:
                    break
        if not cover_url:
            image = item.get("image") or {}
            cover_url = self.image_url_from_bucket(image.get("bucketPath"))

        trailer_url = None
        video = item.get("video") or {}
        if video.get("embedUrl"):
            trailer_url = video["embedUrl"]
        elif video.get("manifestUrl"):
            trailer_url = video["manifestUrl"]
        if not trailer_url:
            trailer_url = f"{self.site}/game/{slug}/"

        genres = [g.get("name") for g in (item.get("genres") or []) if g.get("name")]

        platforms: list[PlatformScore] = []
        for p in item.get("platforms") or []:
            ps = p.get("criticScoreSummary") or {}
            user_score = None
            stats = self.fetch_user_stats(slug, p.get("slug", ""))
            if stats:
                user_score = stats.get("data", {}).get("item", {}).get("score")
            platforms.append(
                PlatformScore(
                    name=p.get("name") or "",
                    slug=p.get("slug") or "",
                    metascore=ps.get("score"),
                    user_score=user_score,
                    is_lead=bool(p.get("isLeadPlatform")),
                )
            )

        critic_reviews = self.fetch_critic_reviews(slug)
        user_reviews = self.fetch_user_reviews(slug)

        return GamePayload(
            slug=slug,
            title=title,
            developer=developer,
            description=description,
            cover_url=cover_url,
            trailer_url=trailer_url,
            metacritic_url=f"{self.site}/game/{slug}/",
            release_date=release_date,
            genres=genres,
            platforms=platforms,
            critic_reviews=critic_reviews,
            user_reviews=user_reviews,
        )


def parse_new_release_slugs_from_html(html: str, limit: int = 100) -> list[str]:
    """Extract game slugs from Metacritic new-releases HTML (stable for tests)."""
    slugs: list[str] = []
    seen: set[str] = set()

    # Prefer structured parsing
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select('a[href*="/game/"]'):
        href = a.get("href") or ""
        m = re.search(r"/game/([a-z0-9][a-z0-9-]*)/", href)
        if not m:
            continue
        slug = m.group(1)
        if slug in {"all", "release-date", "ps5", "pc", "xbox-series-x"}:
            continue
        if slug not in seen:
            seen.add(slug)
            slugs.append(slug)
        if len(slugs) >= limit:
            break

    if slugs:
        return slugs

    # Fallback regex on raw HTML
    for m in re.finditer(r"/game/([a-z0-9][a-z0-9-]*)/", html):
        slug = m.group(1)
        if slug in {"all", "release-date", "ps5", "pc", "xbox-series-x"}:
            continue
        if slug not in seen:
            seen.add(slug)
            slugs.append(slug)
        if len(slugs) >= limit:
            break
    return slugs


def parse_finder_items(data: dict) -> list[dict]:
    """Normalize finder API JSON into minimal dicts (for tests)."""
    items = data.get("data", {}).get("items", [])
    result = []
    for item in items:
        result.append(
            {
                "slug": item.get("slug"),
                "title": item.get("title"),
                "release_date": item.get("releaseDate"),
            }
        )
    return result
