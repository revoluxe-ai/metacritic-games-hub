from types import SimpleNamespace

from app.models import Game
from app.services.similar import find_similar


def _game(id_: int, slug: str, title: str, **kw) -> Game:
    g = Game(id=id_, slug=slug, title=title)
    g.genres = kw.get("genres", [])
    g.description = kw.get("description", "")
    g.developer = kw.get("developer", "")
    g.description_embedding_text = kw.get("extra", "")
    g.platforms = []
    return g


def test_find_similar_prefers_same_genre():
    target = _game(1, "elden-ring", "Elden Ring", genres=["Action RPG"], description="open world souls")
    other = _game(2, "hades-ii", "Hades II", genres=["Roguelike"], description="underworld rogue")
    similar = _game(3, "bg3", "Baldur's Gate 3", genres=["RPG"], description="party adventure open world")
    result = find_similar([target, other, similar], target, limit=2)
    assert result
    assert result[0].slug in {"bg3", "hades-ii"}
