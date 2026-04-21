from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..utils import load_env_file, project_root


@dataclass(frozen=True)
class StructuredGenerationResult:
    parsed: Any
    raw_text: str


def load_openai_env_config(env_path: Path | None = None, include_env_file: bool = True) -> dict[str, str]:
    if include_env_file:
        load_env_file(env_path or (project_root() / ".env"))
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Missing required environment variables in .env or process environment: OPENAI_API_KEY"
        )
    return {"OPENAI_API_KEY": api_key}


class OpenAIJsonClient:
    def __init__(self, api_key: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise ImportError("openai is required to run the extraction client") from exc

        self.client = OpenAI(api_key=api_key)

    @classmethod
    def from_env(cls) -> "OpenAIJsonClient":
        required = load_openai_env_config()
        return cls(api_key=required["OPENAI_API_KEY"])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_structured(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        response_model: type[Any],
    ) -> StructuredGenerationResult:
        completion = self.client.chat.completions.parse(
            model=model,
            messages=messages,
            temperature=0,
            response_format=response_model,
        )
        message = completion.choices[0].message
        if message.parsed is None:
            if message.refusal:
                raise ValueError(f"Model refusal: {message.refusal}")
            raise ValueError("Structured parse returned no parsed object")
        return StructuredGenerationResult(
            parsed=message.parsed,
            raw_text=message.content if isinstance(message.content, str) else str(message.content or ""),
        )


class OpenAIAgentsStructuredClient:
    def __init__(self, api_key: str) -> None:
        try:
            from agents import Agent, ModelSettings, Runner, set_default_openai_key
            from agents.model_settings import Reasoning
        except ImportError as exc:  # pragma: no cover
            raise ImportError("openai-agents is required to run the multi-stage extraction client") from exc

        set_default_openai_key(api_key, use_for_tracing=False)
        self._Agent = Agent
        self._ModelSettings = ModelSettings
        self._Reasoning = Reasoning
        self._Runner = Runner

    @classmethod
    def from_env(cls) -> "OpenAIAgentsStructuredClient":
        required = load_openai_env_config()
        return cls(api_key=required["OPENAI_API_KEY"])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_structured_via_agent(
        self,
        *,
        agent_name: str,
        model: str,
        reasoning_effort: str,
        instructions: str,
        input_text: str,
        response_model: type[Any],
    ) -> StructuredGenerationResult:
        agent = self._Agent(
            name=agent_name,
            instructions=instructions,
            model=model,
            model_settings=self._ModelSettings(
                reasoning=self._Reasoning(effort=reasoning_effort),
            ),
            output_type=response_model,
        )
        result = self._Runner.run_sync(agent, input=input_text, max_turns=1)
        parsed = result.final_output_as(response_model, raise_if_incorrect_type=True)
        raw_text = parsed.model_dump_json(indent=2, exclude_none=True) if hasattr(parsed, "model_dump_json") else str(parsed)
        return StructuredGenerationResult(parsed=parsed, raw_text=raw_text)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(lambda exc: exc.__class__.__name__ != "MaxTurnsExceeded"),
    )
    def generate_structured_via_agent_with_tools(
        self,
        *,
        agent_name: str,
        model: str,
        reasoning_effort: str,
        instructions: str,
        input_text: str,
        response_model: type[Any],
        tools: list[Any],
        max_turns: int,
    ) -> StructuredGenerationResult:
        agent = self._Agent(
            name=agent_name,
            instructions=instructions,
            model=model,
            model_settings=self._ModelSettings(
                reasoning=self._Reasoning(effort=reasoning_effort),
            ),
            tools=tools,
            output_type=response_model,
        )
        result = self._Runner.run_sync(agent, input=input_text, max_turns=max_turns)
        parsed = result.final_output_as(response_model, raise_if_incorrect_type=True)
        raw_text = parsed.model_dump_json(indent=2, exclude_none=True) if hasattr(parsed, "model_dump_json") else str(parsed)
        return StructuredGenerationResult(parsed=parsed, raw_text=raw_text)
