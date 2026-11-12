from unittest.mock import MagicMock, patch

import pytest
from openai import APIStatusError, RateLimitError

from app.services.llm import chat_completion_with_retry


def _mock_response(status_code: int) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.request = MagicMock()
    return resp


def test_chat_completion_retries_on_503():
    client = MagicMock()
    ok = MagicMock()
    client.chat.completions.create.side_effect = [
        APIStatusError("overloaded", response=_mock_response(503), body=None),
        ok,
    ]
    with patch("app.services.llm.get_settings") as gs:
        gs.return_value.llm_max_retries = 2
        gs.return_value.llm_retry_backoff_seconds = 0.01
        result = chat_completion_with_retry(client, model="gemini-3.1-flash-lite", messages=[])
    assert result is ok
    assert client.chat.completions.create.call_count == 2


def test_chat_completion_retries_on_429():
    client = MagicMock()
    ok = MagicMock()
    client.chat.completions.create.side_effect = [
        RateLimitError("rate", response=_mock_response(429), body=None),
        ok,
    ]
    with patch("app.services.llm.get_settings") as gs:
        gs.return_value.llm_max_retries = 2
        gs.return_value.llm_retry_backoff_seconds = 0.01
        result = chat_completion_with_retry(client, model="gemini-3.1-flash-lite", messages=[])
    assert result is ok


def test_chat_completion_raises_after_retries():
    client = MagicMock()
    client.chat.completions.create.side_effect = APIStatusError(
        "rate", response=_mock_response(429), body=None
    )
    with patch("app.services.llm.get_settings") as gs:
        gs.return_value.llm_max_retries = 1
        gs.return_value.llm_retry_backoff_seconds = 0.01
        with pytest.raises(APIStatusError):
            chat_completion_with_retry(client, model="x", messages=[])
