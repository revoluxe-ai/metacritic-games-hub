from app.template_filters import (
    format_date,
    metascore_badge,
    metascore_class,
    render_summary,
    userscore_badge,
    userscore_class,
)


def test_format_date_iso():
    assert format_date("2026-11-05") == "5 Nov 2026"
    assert format_date("") == "TBD"
    assert format_date(None) == "TBD"


def test_score_thresholds():
    assert metascore_class(96) == "score-good"
    assert metascore_class(69) == "score-mixed"
    assert metascore_class(42) == "score-bad"
    assert metascore_class(None) == "score-tbd"
    assert userscore_class(9.6) == "score-good"
    assert userscore_class(7.5) == "score-good"
    assert userscore_class(6.1) == "score-mixed"
    assert userscore_class(0.0) == "score-tbd"
    assert userscore_class(None) == "score-tbd"


def test_badges_escape_and_labels():
    assert "96" in metascore_badge(96)
    assert "score-good" in metascore_badge(96)
    assert "9.6" in userscore_badge(9.6)
    assert "tbd" in userscore_badge(0)
    assert "tbd" in metascore_badge(None)


def test_render_summary_markdown():
    raw = (
        "**What people like:**\n\n"
        "*   **Timeless core design:** The original gameplay remains captivating.\n"
        "*   **Modernized presentation:** Beautiful, detailed graphics.\n\n"
        "**What people dislike:**\n\n"
        "*   *No specific dislikes were mentioned in the provided excerpts.*\n"
    )
    html = str(render_summary(raw))
    assert "**" not in html
    assert html.count("<h3") == 2
    assert "<strong>Timeless core design:</strong>" in html
    assert "<em>No specific dislikes were mentioned in the provided excerpts.</em>" in html
    assert "<ul>" in html
    assert "&lt;" not in html or "script" not in raw


def test_render_summary_escapes_html_and_empty():
    html = str(render_summary("<script>alert(1)</script>"))
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    empty = str(render_summary(None))
    assert "Not summarized yet." in empty
