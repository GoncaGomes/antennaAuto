from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import BaseModel
from tenacity import wait_none

from mvp.llm.client import OpenAIAgentsStructuredClient, OpenAIJsonClient, load_openai_env_config


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


class DummyResponse(BaseModel):
    value: str


def test_openai_json_client_retries_transient_failures() -> None:
    client = object.__new__(OpenAIJsonClient)
    attempts = {"count": 0}

    def parse(**kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary failure")
        message = SimpleNamespace(parsed=DummyResponse(value="ok"), refusal=None, content='{"value":"ok"}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    client.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    original_wait = OpenAIJsonClient.generate_structured.retry.wait
    OpenAIJsonClient.generate_structured.retry.wait = wait_none()
    try:
        result = client.generate_structured(
            model="gpt-4o",
            messages=[{"role": "user", "content": "test"}],
            response_model=DummyResponse,
        )
    finally:
        OpenAIJsonClient.generate_structured.retry.wait = original_wait

    assert attempts["count"] == 3
    assert result.parsed.value == "ok"


def test_agents_client_retries_transient_failures() -> None:
    client = object.__new__(OpenAIAgentsStructuredClient)
    attempts = {"count": 0}

    class FakeRunner:
        @staticmethod
        def run_sync(agent, input, max_turns):
            attempts["count"] += 1
            if attempts["count"] < 3:
                raise RuntimeError("temporary failure")

            class FakeResult:
                @staticmethod
                def final_output_as(response_model, raise_if_incorrect_type=True):
                    return response_model(value="ok")

            return FakeResult()

    client._Agent = lambda **kwargs: kwargs
    client._ModelSettings = lambda **kwargs: kwargs
    client._Reasoning = lambda **kwargs: kwargs
    client._Runner = FakeRunner
    original_wait = OpenAIAgentsStructuredClient.generate_structured_via_agent.retry.wait
    OpenAIAgentsStructuredClient.generate_structured_via_agent.retry.wait = wait_none()
    try:
        result = client.generate_structured_via_agent(
            agent_name="test_agent",
            model="gpt-5.4-mini",
            reasoning_effort="medium",
            instructions="test instructions",
            input_text="test input",
            response_model=DummyResponse,
        )
    finally:
        OpenAIAgentsStructuredClient.generate_structured_via_agent.retry.wait = original_wait

    assert attempts["count"] == 3
    assert result.parsed.value == "ok"
