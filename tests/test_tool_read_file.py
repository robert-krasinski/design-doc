import json
import os
import sys
from pathlib import Path

import pytest
from openai import OpenAI

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from config import configure_llm_defaults
from tools.repo_reader import read_file


def _get_base_url() -> str | None:
    # Prefer explicit local LLM configuration, then OpenAI-compatible overrides.
    return (
        os.environ.get("LOCAL_LLM_BASE_URL")
        or os.environ.get("OPENAI_API_BASE")
        or os.environ.get("OPENAI_BASE_URL")
    )


def _get_model() -> str | None:
    # Keep model resolution aligned with the main app defaults.
    return (
        os.environ.get("LOCAL_LLM_MODEL")
        or os.environ.get("OPENAI_MODEL_NAME")
        or os.environ.get("MODEL")
    )


def _normalize_base_url(base_url: str) -> str:
    # OpenAI client expects /v1 base path.
    base = base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    return base


def test_tool_read_file() -> None:
    # Integration-style test: ensure tool-calling can read a local file.
    configure_llm_defaults()
    base_url = _get_base_url()
    model = _get_model()

    if not base_url or not model:
        pytest.fail(
            "Local LLM not configured. Set LOCAL_LLM_BASE_URL and LOCAL_LLM_MODEL."
        )

    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY", "local"), base_url=_normalize_base_url(base_url))

    tools = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file relative to the project root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            },
        }
    ]

    messages = [
        {
            "role": "user",
            "content": "Use the read_file tool to read inputs/context.md and return only the file contents.",
        }
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="auto",
    )

    assert response.choices, "No choices returned from LLM"
    message = response.choices[0].message
    tool_calls = message.tool_calls or []
    assert tool_calls, "LLM did not issue a tool call"

    tool_call = tool_calls[0]
    raw_args = tool_call.function.arguments
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
    except json.JSONDecodeError as exc:
        pytest.fail(f"Tool call arguments are not valid JSON: {exc}")

    assert args.get("path") == "inputs/context.md", "Tool call path mismatch"

    file_content = read_file("inputs/context.md")
    assert file_content, "read_file returned empty content"

    if message.content:
        assert message.content.strip() == file_content.strip(), "LLM response content does not match file"
