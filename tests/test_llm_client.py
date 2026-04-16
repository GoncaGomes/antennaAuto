from __future__ import annotations

import pytest

from mvp.llm.client import load_openai_env_config


@pytest.fixture(autouse=True)
def clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ["OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_CHANNEL_ID", "NEW_OPENAI_API_KEY"]:
        monkeypatch.delenv(key, raising=False)


def test_llm_env_uses_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "official-key")

    config = load_openai_env_config(include_env_file=False)

    assert config == {"OPENAI_API_KEY": "official-key"}


def test_llm_env_requires_openai_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(RuntimeError) as exc_info:
        load_openai_env_config(include_env_file=False)

    message = str(exc_info.value)
    assert "OPENAI_API_KEY" in message
