"""OpenAI-compatible LLM with heuristic fallback."""

from __future__ import annotations

import re
from collections import Counter

from openai import OpenAI

from app.config import get_settings
from app.services.metacritic import GamePayload, ReviewSnippet


def _heuristic_summary(reviews: list[ReviewSnippet], audience: str) -> str:
    if not reviews:
        return f"No {audience} reviews available yet."

    scores = [r.score for r in reviews if r.score is not None]
    avg = sum(scores) / len(scores) if scores else None
    positive = [r for r in reviews if r.score is not None and float(r.score) >= 70]
    negative = [r for r in reviews if r.score is not None and float(r.score) < 50]

    likes: list[str] = []
    dislikes: list[str] = []
    for r in positive[:5]:
        if r.quote:
            likes.append(r.quote[:180])
    for r in negative[:5]:
        if r.quote:
            dislikes.append(r.quote[:180])

    if not likes and reviews:
        likes = [reviews[0].quote[:180]] if reviews[0].quote else []
    if not dislikes and len(reviews) > 1:
        dislikes = [reviews[-1].quote[:180]] if reviews[-1].quote else []

    avg_str = f" Average score: {avg:.1f}." if avg is not None else ""
    like_txt = " ".join(likes[:3]) if likes else "Reviewers highlight solid fundamentals."
    dislike_txt = (
        " ".join(dislikes[:3]) if dislikes else "Few consistent complaints in recent reviews."
    )
    return (
        f"{audience.capitalize()} sentiment (heuristic fallback{avg_str}) "
        f"Likes: {like_txt} "
        f"Dislikes: {dislike_txt}"
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
            return _heuristic_summary(reviews, audience)

        snippets = "\n".join(
            f"- ({r.score}) {r.quote[:400]}"
            for r in reviews[:12]
            if r.quote
        )
        if not snippets:
            return _heuristic_summary(reviews, audience)

        prompt = (
            f"Summarize what {audience} like and dislike about the game "
            f"'{game.title}' based on these Metacritic review excerpts.\n"
            "Write 2 short paragraphs: first 'What people like', then 'What people dislike'.\n"
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
            return _heuristic_summary(reviews, audience)

    def youtube_takeaway(self, game_title: str, transcript_excerpt: str) -> str:
        if not transcript_excerpt.strip():
            return "No let's-play transcript available for this title."

        if not self.enabled or not self._client:
            likes, dislikes = _keyword_heuristic(transcript_excerpt)
            return (
                f"Popular let's-play takeaway (heuristic): "
                f"The streamer focused on {likes}. "
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
                f"Popular let's-play takeaway (heuristic): "
                f"The streamer focused on {likes}. "
                f"Friction points mentioned: {dislikes}."
            )
