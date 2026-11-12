"""OpenAI-compatible LLM with heuristic fallback (Gemini default)."""

from __future__ import annotations

import logging
import re
import time
from collections import Counter

from openai import APIStatusError, OpenAI, RateLimitError

from app.config import get_settings
from app.services.metacritic import GamePayload, ReviewSnippet

log = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 503, 502, 504}


def _first_sentence(quote: str, max_len: int = 200) -> str:
    quote = quote.strip()
    if not quote:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", quote)
    sentence = parts[0] if parts else quote
    if len(sentence) > max_len:
        sentence = sentence[: max_len - 1].rstrip() + "…"
    return sentence


def _heuristic_summary(reviews: list[ReviewSnippet], audience: str, *, critics: bool) -> str:
    if not reviews:
        return (
            f"What people like:\n"
            f"- Not enough {audience} reviews yet to summarize.\n\n"
            f"What people dislike:\n"
            f"- No recurring complaints reported yet."
        )

    if critics:
        pos_threshold, neg_threshold = 70, 49
    else:
        pos_threshold, neg_threshold = 7.0, 4.9

    scores = [float(r.score) for r in reviews if r.score is not None]
    avg = sum(scores) / len(scores) if scores else None

    positive = [
        r for r in reviews if r.score is not None and float(r.score) >= pos_threshold and r.quote
    ]
    negative = [
        r for r in reviews if r.score is not None and float(r.score) <= neg_threshold and r.quote
    ]
    mixed = [
        r
        for r in reviews
        if r.score is not None
        and neg_threshold < float(r.score) < pos_threshold
        and r.quote
    ]

    like_lines: list[str] = []
    for r in positive[:4]:
        like_lines.append(f"- {_first_sentence(r.quote)}")
    if not like_lines:
        for r in mixed[:3]:
            like_lines.append(f"- {_first_sentence(r.quote)}")
    if not like_lines:
        for r in reviews:
            if r.quote and r.score is not None and float(r.score) >= pos_threshold:
                like_lines.append(f"- {_first_sentence(r.quote)}")
                break
    if not like_lines:
        like_lines.append("- Reviewers praise specific strengths but scores are mixed in this sample.")

    dislike_lines: list[str] = []
    for r in negative[:4]:
        dislike_lines.append(f"- {_first_sentence(r.quote)}")
    if not dislike_lines and len(reviews) > 1:
        for r in reviews[-3:]:
            if r.quote and r.score is not None and float(r.score) <= (pos_threshold if critics else 6.0):
                dislike_lines.append(f"- {_first_sentence(r.quote)}")
    if not dislike_lines:
        dislike_lines.append("- No strong negative themes in the latest sampled reviews.")

    avg_block = ""
    if avg is not None:
        label = "Average Metascore" if critics else "Average user score"
        avg_block = f"({label}: {avg:.1f})\n"

    return (
        "What people like:\n"
        + avg_block
        + "\n".join(like_lines)
        + "\n\nWhat people dislike:\n"
        + "\n".join(dislike_lines)
    )


def _keyword_heuristic(text: str) -> tuple[str, str]:
    tokens = re.findall(r"[a-zA-Z']{4,}", text.lower())
    stop = {
        "that",
        "this",
        "with",
        "from",
        "have",
        "game",
        "games",
        "very",
        "really",
        "about",
        "their",
        "there",
        "which",
        "would",
        "could",
        "should",
    }
    filtered = [t for t in tokens if t not in stop]
    common = Counter(filtered).most_common(8)
    if not common:
        return "Gameplay and presentation", "Technical polish"
    likes = ", ".join(w for w, _ in common[:4])
    dislikes = ", ".join(w for w, _ in common[4:8]) or "Minor bugs or pacing"
    return likes, dislikes


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code in _RETRYABLE_STATUS
    return False


def chat_completion_with_retry(client: OpenAI, **kwargs):
    """Single-flight chat call with exponential backoff on 429/503 (free-tier friendly)."""
    settings = get_settings()
    last_exc: BaseException | None = None
    for attempt in range(settings.llm_max_retries + 1):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            if not _is_retryable(exc) or attempt >= settings.llm_max_retries:
                raise
            last_exc = exc
            delay = settings.llm_retry_backoff_seconds * (2**attempt)
            log.warning("LLM retry %s after %ss: %s", attempt + 1, delay, exc)
            time.sleep(delay)
    if last_exc:
        raise last_exc
    raise RuntimeError("chat_completion_with_retry exhausted without result")


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = bool(settings.llm_api_key)
        self.model = settings.llm_model
        self._client: OpenAI | None = None
        if self.enabled:
            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
                max_retries=0,
            )

    def _throttle(self) -> None:
        settings = get_settings()
        if self.enabled and settings.llm_request_delay_seconds > 0:
            time.sleep(settings.llm_request_delay_seconds)

    def summarize_reviews(
        self, game: GamePayload, critic: bool
    ) -> str:
        reviews = game.critic_reviews if critic else game.user_reviews
        audience = "critics" if critic else "users"
        if not self.enabled or not self._client:
            return _heuristic_summary(reviews, audience, critics=critic)

        settings = get_settings()
        snippets = "\n".join(
            f"- ({r.score}) {r.quote[:250]}"
            for r in reviews[: settings.llm_max_review_snippets]
            if r.quote
        )
        if not snippets:
            return _heuristic_summary(reviews, audience, critics=critic)

        prompt = (
            f"Summarize what {audience} like and dislike about '{game.title}' "
            "from these Metacritic excerpts only.\n"
            "Headings: What people like: / What people dislike:\n"
            "Use 2-4 short bullets each. No invented facts.\n\n"
            f"{snippets}"
        )
        try:
            self._throttle()
            resp = chat_completion_with_retry(
                self._client,
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Concise English game-review summaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.llm_max_output_tokens,
                temperature=0.3,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM summarize_reviews failed, using heuristic: %s", exc)
            return _heuristic_summary(reviews, audience, critics=critic)

    def youtube_takeaway(self, game_title: str, transcript_excerpt: str) -> str:
        if not transcript_excerpt.strip():
            return "No let's-play transcript available for this title."

        if not self.enabled or not self._client:
            likes, dislikes = _keyword_heuristic(transcript_excerpt)
            return (
                f"What the streamer highlights: {likes}.\n"
                f"Friction points mentioned: {dislikes}."
            )

        settings = get_settings()
        prompt = (
            f"From this let's-play transcript for '{game_title}', "
            "write 2-3 sentences on gameplay/story/difficulty and one shopper takeaway.\n\n"
            f"{transcript_excerpt[: settings.llm_max_transcript_chars]}"
        )
        try:
            self._throttle()
            resp = chat_completion_with_retry(
                self._client,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=min(settings.llm_max_output_tokens, 220),
                temperature=0.4,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as exc:  # noqa: BLE001
            log.warning("LLM youtube_takeaway failed, using heuristic: %s", exc)
            likes, dislikes = _keyword_heuristic(transcript_excerpt)
            return (
                f"What the streamer highlights: {likes}.\n"
                f"Friction points mentioned: {dislikes}."
            )
