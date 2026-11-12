"""OpenAI-compatible LLM with heuristic fallback."""

from __future__ import annotations

import re
from collections import Counter

from openai import OpenAI

from app.config import get_settings
from app.services.metacritic import GamePayload, ReviewSnippet


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


class LLMService:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = bool(settings.llm_api_key)
        self.model = settings.llm_model
        self._client = None
        if self.enabled:
            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )

    def summarize_reviews(
        self, game: GamePayload, critic: bool
    ) -> str:
        reviews = game.critic_reviews if critic else game.user_reviews
        audience = "critics" if critic else "users"
        if not self.enabled or not self._client:
            return _heuristic_summary(reviews, audience, critics=critic)

        snippets = "\n".join(
            f"- ({r.score}) {r.quote[:400]}"
            for r in reviews[:12]
            if r.quote
        )
        if not snippets:
            return _heuristic_summary(reviews, audience, critics=critic)

        prompt = (
            f"Summarize what {audience} like and dislike about the game "
            f"'{game.title}' based on these Metacritic review excerpts.\n"
            "Use exactly these headings:\n"
            "What people like:\n"
            "(bullet points)\n\n"
            "What people dislike:\n"
            "(bullet points)\n"
            "Be specific; do not invent facts not supported by the quotes.\n\n"
            f"{snippets}"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You write concise English summaries for a game catalog.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=350,
                temperature=0.3,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception:
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

        prompt = (
            f"From this YouTube let's-play transcript excerpt for '{game_title}', "
            "write 3-4 sentences on what the creator emphasizes (gameplay feel, "
            "difficulty, story, bugs) and a one-line conclusion for shoppers.\n\n"
            f"{transcript_excerpt[:6000]}"
        )
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                max_tokens=280,
                temperature=0.4,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception:
            likes, dislikes = _keyword_heuristic(transcript_excerpt)
            return (
                f"What the streamer highlights: {likes}.\n"
                f"Friction points mentioned: {dislikes}."
            )
