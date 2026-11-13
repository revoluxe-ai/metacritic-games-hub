"""Jinja filters for dates, Metacritic-style score badges, and LLM summaries."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from markupsafe import Markup, escape

_DATE_FORMATS = (
    ("%Y-%m-%d", 10),
    ("%Y-%m-%dT%H:%M:%S", 19),
    ("%Y-%m", 7),
    ("%b %d, %Y", None),
    ("%B %d, %Y", None),
)


def format_date(value: Any) -> str:
    """Render a stored date string as '5 Nov 2026'. Unknown values pass through."""
    if value is None:
        return "TBD"
    if hasattr(value, "strftime") and hasattr(value, "day"):
        return f"{value.day} {value.strftime('%b %Y')}"
    text = str(value).strip()
    if not text:
        return "TBD"
    for fmt, size in _DATE_FORMATS:
        piece = text[:size] if size else text
        # Strip fractional seconds for ISO datetimes
        if "T" in piece and fmt.startswith("%Y-%m-%dT"):
            piece = re.sub(r"\.\d+$", "", piece)
        try:
            dt = datetime.strptime(piece, fmt)
            return f"{dt.day} {dt.strftime('%b %Y')}"
        except ValueError:
            continue
    return text


def _has_userscore(score: Any) -> bool:
    return score is not None and score != "" and float(score) > 0


def metascore_class(score: Any) -> str:
    if score is None or score == "":
        return "score-tbd"
    value = int(score)
    if value >= 75:
        return "score-good"
    if value >= 50:
        return "score-mixed"
    return "score-bad"


def userscore_class(score: Any) -> str:
    if not _has_userscore(score):
        return "score-tbd"
    value = float(score)
    if value >= 7.5:
        return "score-good"
    if value >= 5.0:
        return "score-mixed"
    return "score-bad"


def metascore_badge(score: Any) -> Markup:
    if score is None or score == "":
        inner, cls = "tbd", "score-tbd"
    else:
        inner, cls = str(int(score)), metascore_class(score)
    return Markup(
        f'<span class="score score-meta {cls}" title="Metascore">{inner}</span>'
    )


def userscore_badge(score: Any) -> Markup:
    if not _has_userscore(score):
        inner, cls = "tbd", "score-tbd"
    else:
        inner, cls = f"{float(score):.1f}", userscore_class(score)
    return Markup(
        f'<span class="score score-user {cls}" title="User score">{inner}</span>'
    )


def _inline_markdown(text: str) -> str:
    """Apply bold/italic to an already HTML-escaped string."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", text)
    text = re.sub(
        r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\*)",
        r"<em>\1</em>",
        text,
    )
    return text


def _looks_like_heading(line: str) -> bool:
    return bool(re.match(r"^\*\*[^*].*\*\*:?\s*$", line))


def _heading_text(line: str) -> str:
    text = re.sub(r"^\*\*(.+?)\*\*:?\s*$", r"\1", line).strip().rstrip(":")
    return text


def _is_bullet(line: str) -> bool:
    return bool(re.match(r"^(\*|-)\s+", line))


def _bullet_body(line: str) -> str:
    return re.sub(r"^(\*|-)\s+", "", line)


def _unescape_llm_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\\n", "\n").replace("\\t", " ")
    text = text.replace("\\'", "'").replace('\\"', '"')
    # Leftover escaped markdown or quotes from JSON round-trips
    text = text.replace("\\*", "*")
    return text.strip()


def render_summary(text: Any) -> Markup:
    """Turn LLM markdown-ish text into safe HTML paragraphs and lists."""
    if text is None or not str(text).strip():
        return Markup('<p class="muted">Not summarized yet.</p>')

    raw = _unescape_llm_text(str(text))
    safe = str(escape(raw))
    blocks = re.split(r"\n\s*\n", safe)
    parts: list[str] = []

    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue

        html_chunks: list[str] = []
        bullets: list[str] = []
        paragraphs: list[str] = []

        def flush_bullets() -> None:
            nonlocal bullets
            if bullets:
                html_chunks.append("<ul>" + "".join(bullets) + "</ul>")
                bullets = []

        def flush_paragraphs() -> None:
            nonlocal paragraphs
            if paragraphs:
                html_chunks.append("<p>" + "<br />".join(paragraphs) + "</p>")
                paragraphs = []

        for line in lines:
            if _looks_like_heading(line):
                flush_paragraphs()
                flush_bullets()
                html_chunks.append(
                    f'<h3 class="summary-heading">{_inline_markdown(_heading_text(line))}</h3>'
                )
            elif _is_bullet(line):
                flush_paragraphs()
                bullets.append(f"<li>{_inline_markdown(_bullet_body(line))}</li>")
            else:
                flush_bullets()
                paragraphs.append(_inline_markdown(line))
        flush_paragraphs()
        flush_bullets()
        parts.extend(html_chunks)

    return Markup('<div class="summary">' + "".join(parts) + "</div>")


def lead_platform(platforms: Any) -> Any:
    if not platforms:
        return None
    for item in platforms:
        if getattr(item, "is_lead", False):
            return item
    return platforms[0]


def register_filters(templates) -> None:
    env = templates.env
    env.filters["format_date"] = format_date
    env.filters["metascore_class"] = metascore_class
    env.filters["userscore_class"] = userscore_class
    env.filters["metascore_badge"] = metascore_badge
    env.filters["userscore_badge"] = userscore_badge
    env.filters["render_summary"] = render_summary
    env.filters["lead_platform"] = lead_platform
