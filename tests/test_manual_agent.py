"""Tests for the Manuals agent."""
from __future__ import annotations

from pathlib import Path

import pytest

import agents.vanilla_agent as vanilla_agent
from agents.manual_agent import ManualAgent
from langchain_core.messages import AIMessage


class FakeListChatModel:
    """Simple fake chat model returning preset responses."""

    def __init__(self, responses):
        self._responses = list(responses)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):  # pragma: no cover - simple passthrough
        return self._responses.pop(0)


def _build_fake_tool_call_model():
    responses = [
        AIMessage(
            content="",
            additional_kwargs={
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "manuals_tool",
                            "arguments": "{\"machine_name\": \"machine001\"}",
                        },
                    }
                ]
            },
        ),
        AIMessage(content="Manual consulted"),
    ]
    return FakeListChatModel(responses)


def _build_fake_final_model():
    responses = [AIMessage(content="saw image")]
    return FakeListChatModel(responses)


@pytest.fixture
def manuals_dir() -> Path:
    return Path(__file__).parent / "data"


def test_agent_invokes_manual_tool(monkeypatch, manuals_dir: Path):
    fake_model = _build_fake_tool_call_model()
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: fake_model)
    monkeypatch.setenv("MANUALS_MD_PATH", str(manuals_dir))
    monkeypatch.setenv("MANUALS_MD_CONNECTION_STRING", "")
    agent = ManualAgent()
    result = agent.invoke(
        {"input": "How do I use it?", "machine_name": "machine001"}
    )
    tool_messages = [m for m in result["messages"] if m.__class__.__name__ == "ToolMessage"]
    assert any("Operator & Maintenance Manual" in m.content for m in tool_messages)
    assert result["messages"][-1].content == "Manual consulted"


def test_agent_accepts_image_input(monkeypatch, manuals_dir: Path):
    fake_model = _build_fake_final_model()
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: fake_model)
    monkeypatch.setenv("MANUALS_MD_PATH", str(manuals_dir))
    monkeypatch.setenv("MANUALS_MD_CONNECTION_STRING", "")
    agent = ManualAgent()
    img_input = [
        {"type": "text", "text": "What is shown?"},
        {"type": "image_url", "image_url": {"url": "http://example.com"}},
    ]
    result = agent.invoke({"input": img_input, "machine_name": "machine001"})
    assert result["messages"][-1].content == "saw image"
