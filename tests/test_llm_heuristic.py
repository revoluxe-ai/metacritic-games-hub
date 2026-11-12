from app.services.llm import LLMService, _heuristic_summary
from app.services.metacritic import GamePayload, ReviewSnippet


def test_heuristic_has_like_dislike_headings():
    reviews = [
        ReviewSnippet(score=90, quote="Excellent combat and world design.", author="Pub"),
        ReviewSnippet(score=40, quote="Camera and performance issues hurt exploration.", author="Pub"),
    ]
    text = _heuristic_summary(reviews, "critics", critics=True)
    assert "What people like:" in text
    assert "What people dislike:" in text
    assert "Excellent combat" in text
    assert "performance issues" in text


def test_llm_service_heuristic_without_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    llm = LLMService()
    game = GamePayload(
        slug="demo",
        title="Demo",
        developer=None,
        description=None,
        cover_url=None,
        trailer_url=None,
        metacritic_url="https://example.com",
        release_date=None,
        critic_reviews=[
            ReviewSnippet(score=8, quote="Fun co-op and great music.", author=None),
        ],
        user_reviews=[
            ReviewSnippet(score=3, quote="Grindy and repetitive quests.", author=None),
        ],
    )
    out = llm.summarize_reviews(game, critic=False)
    assert "What people like:" in out
    assert "What people dislike:" in out
