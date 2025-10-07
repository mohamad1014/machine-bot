from __future__ import annotations

import json

import pytest
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

import agents.vanilla_agent as vanilla_agent
import agents.logging_utils as logging_utils
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

    def run(self, *args: Any, **kwargs: Any) -> ToolMessage:  # type: ignore[unused-argument]
        if args and isinstance(args[0], dict):
            self.calls.append(args[0])
        elif "query" in kwargs:
            self.calls.append({"query": kwargs["query"]})
        else:
            self.calls.append({"args": list(args), "kwargs": dict(kwargs)})
        return ToolMessage(
            content=self.payload,
            name=self.name,
            tool_call_id=kwargs.get("tool_call_id") or "stub-search-call",
        )

    def invoke(self, args: dict[str, Any]) -> ToolMessage:
        call_args: dict[str, Any]
        if "args" in args and isinstance(args["args"], dict):
            call_args = args["args"]
        elif isinstance(args, dict):
            call_args = args
        else:
            call_args = {}
        if isinstance(call_args, dict):
            self.calls.append(call_args)
        return ToolMessage(
            content=self.payload,
            name=self.name,
            tool_call_id=args.get("id") or "stub-search-call",
        )

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

    def run(self, *args: Any, **kwargs: Any) -> ToolMessage:  # type: ignore[unused-argument]
        self.calls.append({"args": args, "kwargs": kwargs})
        return ToolMessage(
            content="{}",
            name=self.name,
            tool_call_id=kwargs.get("tool_call_id") or "stub-content-call",
        )

    def invoke(self, args: dict[str, Any]) -> ToolMessage:
        self.calls.append({"args": (), "kwargs": args})
        return ToolMessage(
            content="{}",
            name=self.name,
            tool_call_id=args.get("id") or "stub-content-call",
        )

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
    monkeypatch.setenv("TESTING_AGENT_SEARCH_INDEX", "docling-rag-documents-v422")
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
    assert tool_instance.config["index_env_var"] == "TESTING_AGENT_SEARCH_INDEX"
    assert StubContentTool.instances
    content_instance = StubContentTool.instances[-1]
    assert content_instance.config["container_env_var"] == "CosmosTestDocumentsContainer"


def test_testing_agent_reports_no_results(monkeypatch):
    StubSearchTool.payload = "No relevant testing reports were found in Azure AI Search."
    StubSearchTool.instances = []
    StubContentTool.instances = []
    monkeypatch.setattr(documents_tools, "DoclingDocumentSearchTool", StubSearchTool)
    monkeypatch.setattr(documents_tools, "DoclingDocumentContentTool", StubContentTool)
    monkeypatch.setenv("TESTING_AGENT_SEARCH_INDEX", "docling-rag-documents-v422")
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
    content_instance = StubContentTool.instances[-1]
    assert content_instance.config["container_env_var"] == "CosmosTestDocumentsContainer"


def test_agent_logging_captures_interactions(monkeypatch):
    payload = "Result payload"
    StubSearchTool.payload = payload
    StubSearchTool.instances = []
    StubContentTool.instances = []
    monkeypatch.setattr(documents_tools, "DoclingDocumentSearchTool", StubSearchTool)
    monkeypatch.setattr(documents_tools, "DoclingDocumentContentTool", StubContentTool)
    monkeypatch.setenv("TESTING_AGENT_SEARCH_INDEX", "docling-rag-documents-v422")
    fake_model = _build_tool_calling_model(payload)
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: fake_model)
    vanilla_agent.VanillaAgent.MEMORY = []

    agent = TestingAgent()

    agent.invoke({"input": "Log the next testing steps"})

    logs = agent.get_logs()
    assert any("received human input" in line for line in logs)
    assert any("final AI response" in line for line in logs)
    assert any("invoking tool docling_documents_search" in line for line in logs)


def test_agent_logging_uploads_to_blob(monkeypatch):
    class StubContainerClient:
        def __init__(self) -> None:
            self.uploads: list[tuple[str, bytes, bool]] = []
            self.container_name: str | None = None

        def upload_blob(self, name: str, data: bytes, overwrite: bool) -> None:
            self.uploads.append((name, data, overwrite))

    stub_container = StubContainerClient()

    class StubBlobServiceClient:
        last_connection_string: str | None = None

        @classmethod
        def from_connection_string(cls, connection_string: str) -> "StubBlobServiceClient":
            cls.last_connection_string = connection_string
            return cls()

        def get_container_client(self, container_name: str) -> StubContainerClient:
            stub_container.container_name = container_name
            return stub_container

    monkeypatch.setenv("AGENT_LOGS_CONTAINER", "agent-logs")
    monkeypatch.setenv("AzureWebJobsStorage", "UseDevelopmentStorage=true")
    monkeypatch.setenv("TESTING_AGENT_SEARCH_INDEX", "docling-rag-documents-v422")
    monkeypatch.setattr(logging_utils, "BlobServiceClient", StubBlobServiceClient)
    monkeypatch.setattr(documents_tools, "DoclingDocumentSearchTool", StubSearchTool)
    monkeypatch.setattr(documents_tools, "DoclingDocumentContentTool", StubContentTool)

    fake_model = FakeListChatModel([AIMessage(content="All good")])
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: fake_model)
    vanilla_agent.VanillaAgent.MEMORY = []

    agent = TestingAgent()
    agent.logging_settings.save_to_blob = True

    agent.invoke({"input": "Upload this log"})

    assert stub_container.uploads, "Expected the agent log to be uploaded"
    blob_name, payload, overwrite = stub_container.uploads[0]
    assert stub_container.container_name == "agent-logs"
    assert StubBlobServiceClient.last_connection_string == "UseDevelopmentStorage=true"
    assert blob_name.endswith(".log")
    assert overwrite is True
    assert "Upload this log" in payload.decode("utf-8")
