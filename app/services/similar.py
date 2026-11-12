"""TF-IDF cosine similarity over stored games."""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models import Game


def _doc(game: Game) -> str:
    genres = " ".join(game.genres or [])
    desc = game.description or ""
    dev = game.developer or ""
    extra = game.description_embedding_text or ""
    return f"{game.title} {genres} {dev} {desc} {extra}"


def find_similar(games: list[Game], target: Game, limit: int = 5) -> list[Game]:
    if len(games) < 2:
        return []

    docs = [_doc(g) for g in games]
    try:
        target_idx = next(i for i, g in enumerate(games) if g.id == target.id)
    except StopIteration:
        return []

    vectorizer = TfidfVectorizer(stop_words="english", max_features=8000)
    matrix = vectorizer.fit_transform(docs)
    sims = cosine_similarity(matrix[target_idx], matrix).flatten()
    ranked = sorted(
        ((i, sims[i]) for i in range(len(games)) if i != target_idx),
        key=lambda x: x[1],
        reverse=True,
    )
    out: list[Game] = []
    for idx, score in ranked[: limit * 2]:
        if score < 0.05:
            continue
        out.append(games[idx])
        if len(out) >= limit:
            break
    return out
