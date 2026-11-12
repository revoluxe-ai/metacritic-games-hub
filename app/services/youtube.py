"""YouTube let's-play discovery + transcript (no Whisper)."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

import httpx
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

USER_AGENT = "Mozilla/5.0 (compatible; SkytecMetacriticHub/1.0)"


def search_lets_play_video_id(game_title: str) -> str | None:
    """Find a popular let's-play via YouTube search results HTML (no API key)."""
    query = quote_plus(f"{game_title} let's play gameplay")
    url = f"https://www.youtube.com/results?search_query={query}"
    try:
        html = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=20).text
    except httpx.HTTPError:
        return None

    ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
    seen: set[str] = set()
    for vid in ids:
        if vid not in seen:
            seen.add(vid)
            return vid
    return None


def fetch_transcript_excerpt(video_id: str, max_chars: int = 8000) -> str:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(
            video_id, languages=["en", "en-US", "en-GB"]
        )
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
        try:
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception:
            return ""

    text = " ".join(entry.get("text", "") for entry in transcript)
    return text[:max_chars]


def lets_play_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"
