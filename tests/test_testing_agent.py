from __future__ import annotations

import json

import pytest
from typing import Any

from langchain_core.messages import AIMessage

import agents.vanilla_agent as vanilla_agent
from agents.testing_agent import TestingAgent
from middleware import documents_tools


class FakeListChatModel:
    """Simple fake chat model returning preset responses."""

    def __init__(self, responses):
        self._responses = list(responses)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        return self._responses.pop(0)


class StubSearchTool:
    """Tool stub that records search invocations and returns canned payloads."""

    name: str = "docling_documents_search"
    payload: str = ""
    instances: list["StubSearchTool"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.calls: list[dict[str, str]] = []
        self.config = kwargs
        StubSearchTool.instances.append(self)

    def run(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[unused-argument]
        if args and isinstance(args[0], dict):
            self.calls.append(args[0])
        elif "query" in kwargs:
            self.calls.append({"query": kwargs["query"]})
        else:
            self.calls.append({"args": list(args), "kwargs": dict(kwargs)})
        return self.payload

    def invoke(self, args: dict[str, Any]) -> str:
        return self.run(args)

    def __call__(self, *args: Any, **kwargs: Any) -> str:
        return self.run(*args, **kwargs)


class StubContentTool:
    """Tool stub that enforces preview/confirm but is not invoked in these tests."""

    name: str = "docling_documents_content"
    instances: list["StubContentTool"] = []

    def __init__(self, **kwargs: Any) -> None:
        self.config = kwargs
        self.calls: list[dict[str, Any]] = []
        StubContentTool.instances.append(self)

    def run(self, *args: Any, **kwargs: Any) -> str:  # type: ignore[unused-argument]
        self.calls.append({"args": args, "kwargs": kwargs})
        return "{}"

    def invoke(self, args: dict[str, Any]) -> str:
        return self.run(args)

def _build_tool_calling_model(payload: str) -> FakeListChatModel:
    tool_call_message = AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "call_1",
                    "function": {
                        "name": "docling_documents_search",
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
    StubSearchTool.payload = payload
    StubSearchTool.instances = []
    StubContentTool.instances = []
    monkeypatch.setattr(documents_tools, "DoclingDocumentSearchTool", StubSearchTool)
    monkeypatch.setattr(documents_tools, "DoclingDocumentContentTool", StubContentTool)
    monkeypatch.setenv("DOCLING_DOCUMENTS_INDEX", "docling-rag-documents-v422")
    fake_model = _build_tool_calling_model(payload)
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: fake_model)
    vanilla_agent.VanillaAgent.MEMORY = []

    agent = TestingAgent()

    result = agent.invoke({"input": "Find calibration steps"})

    assert StubSearchTool.instances, "Tool should be instantiated from configuration."
    tool_instance = StubSearchTool.instances[-1]
    tool_messages = [
        message
        for message in result["messages"]
        if message.__class__.__name__ == "ToolMessage"
    ]
    assert tool_messages, "The tool message should be present in the conversation."
    assert payload in tool_messages[0].content
    assert result["messages"][-1].content == "Search complete"
    assert tool_instance.calls and tool_instance.calls[0]["query"] == "test query"
    assert tool_instance.config["index_env_var"] == "DOCLING_DOCUMENTS_INDEX"
    assert StubContentTool.instances
    content_instance = StubContentTool.instances[-1]
    assert content_instance.config["index_env_var"] == "DOCLING_DOCUMENTS_INDEX"
    assert content_instance.config["metadata_fields"] == [
        "abstract",
        "tags",
        "source_url",
    ]


def test_testing_agent_reports_no_results(monkeypatch):
    StubSearchTool.payload = "No relevant testing reports were found in Azure AI Search."
    StubSearchTool.instances = []
    StubContentTool.instances = []
    monkeypatch.setattr(documents_tools, "DoclingDocumentSearchTool", StubSearchTool)
    monkeypatch.setattr(documents_tools, "DoclingDocumentContentTool", StubContentTool)
    monkeypatch.setenv("DOCLING_DOCUMENTS_INDEX", "docling-rag-documents-v422")
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
