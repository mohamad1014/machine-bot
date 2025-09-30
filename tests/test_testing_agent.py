from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

import agents.vanilla_agent as vanilla_agent
from agents.testing_agent import TestingAgent
from middleware import testing_reports


class FakeListChatModel:
    """Simple fake chat model returning preset responses."""

    def __init__(self, responses):
        self._responses = list(responses)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return self._responses.pop(0)


class StubTool:
    """Tool stub that records invocations and returns canned payloads."""

    name = "testing_reports_search"

    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[dict[str, str]] = []

    def run(self, *args, **kwargs):  # type: ignore[unused-argument]
        if args and isinstance(args[0], dict):
            self.calls.append(args[0])
        elif "query" in kwargs:
            self.calls.append({"query": kwargs["query"]})
        return self.payload


def _build_tool_calling_model(payload: str) -> FakeListChatModel:
    tool_call_message = AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "testing_reports_search",
                        "arguments": json.dumps({"query": "test query"}),
                    },
                }
            ]
        },
    )
    final_message = AIMessage(content="Search complete")
    return FakeListChatModel([tool_call_message, final_message])


def test_testing_agent_invokes_search_tool(monkeypatch):
    payload = "Result payload"
    fake_tool = StubTool(payload)
    monkeypatch.setattr(
        testing_reports, "TestingReportsSearchTool", lambda **_: fake_tool
    )
    fake_model = _build_tool_calling_model(payload)
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: fake_model)
    vanilla_agent.VanillaAgent.MEMORY = []

    agent = TestingAgent()

    result = agent.invoke({"input": "Find calibration steps"})

    tool_messages = [
        message
        for message in result["messages"]
        if message.__class__.__name__ == "ToolMessage"
    ]
    assert tool_messages, "The tool message should be present in the conversation."
    assert payload in tool_messages[0].content
    assert result["messages"][-1].content == "Search complete"
    assert fake_tool.calls and fake_tool.calls[0]["query"] == "test query"


def test_testing_agent_reports_no_results(monkeypatch):
    fake_tool = StubTool("No relevant testing reports were found in Azure AI Search.")
    monkeypatch.setattr(
        testing_reports, "TestingReportsSearchTool", lambda **_: fake_tool
    )
    fake_model = _build_tool_calling_model("unused")
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: fake_model)
    vanilla_agent.VanillaAgent.MEMORY = []

    agent = TestingAgent()
    result = agent.invoke({"input": "Any query"})

    tool_messages = [
        message
        for message in result["messages"]
        if message.__class__.__name__ == "ToolMessage"
    ]
    assert tool_messages
    assert "No relevant testing reports" in tool_messages[-1].content