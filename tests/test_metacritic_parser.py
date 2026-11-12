import json
from pathlib import Path

from app.services.metacritic import (
    MetacriticClient,
    parse_finder_items,
    parse_new_release_slugs_from_html,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_new_release_slugs():
    html = (FIXTURES / "new_releases_snippet.html").read_text()
    slugs = parse_new_release_slugs_from_html(html)
    assert slugs == [
        "phantom-blade-zero",
        "call-of-duty-modern-warfare-4",
        "final-fantasy-resonance",
    ]


def test_parse_finder_items():
    data = json.loads((FIXTURES / "finder_newest.json").read_text())
    items = parse_finder_items(data)
    assert len(items) == 2
    assert items[0]["slug"] == "demo-game-one"


def test_image_url_from_bucket():
    url = MetacriticClient.image_url_from_bucket("/provider/6/12/6-1-824956-52.jpg")
    assert url.endswith("6-1-824956-52.jpg")
    assert "metacritic.com/a/img/catalog" in url
