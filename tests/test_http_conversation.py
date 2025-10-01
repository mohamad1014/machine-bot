"""Tests for the HTTP conversation Azure Function."""
from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import azure.functions as func
from langchain_core.messages import AIMessage, HumanMessage

from functions import http_conversation


class DummyGraph:
    def __init__(self, result):
        self._result = result
        self.invocations = []

    def invoke(self, state):  # pragma: no cover - simple passthrough
        self.invocations.append(state)
        return self._result


class DummyStore:
    def __init__(self):
        self.records: dict[str, list] = {}
        self.deleted: list[str] = []

    def load_messages(self, conversation_id: str):
        return self.records.get(conversation_id, [])

    def save_messages(self, conversation_id: str, messages):
        self.records[conversation_id] = list(messages)

    def delete(self, conversation_id: str):
        self.records.pop(conversation_id, None)
        self.deleted.append(conversation_id)


def _make_request(body: dict) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/conversationRun",
        headers={"Content-Type": "application/json"},
        params={},
        route_params={},
        body=json.dumps(body).encode(),
    )


def test_conversation_run_plain_text(monkeypatch):
    store = DummyStore()
    store.records["conv-1"] = [HumanMessage(content="previous")]
    result_messages = [
        HumanMessage(content="previous"),
        HumanMessage(content="hello"),
        AIMessage(content="text response"),
    ]
    graph = DummyGraph({"messages": result_messages})
    monkeypatch.setattr(http_conversation, "_graph", graph)
    monkeypatch.setattr(http_conversation, "_store", store)

    req = _make_request({"conversation_id": "conv-1", "input": "hello"})
    resp = http_conversation.conversation_run(req)

    assert resp.status_code == 200
    assert json.loads(resp.get_body()) == {"output": "text response"}
    assert store.records["conv-1"] == result_messages
    assert len(graph.invocations) == 1
    invoked_messages = graph.invocations[0]["messages"]
    assert invoked_messages[0].content == "previous"
    assert invoked_messages[-1].content == "hello"


def test_conversation_run_multimodal(monkeypatch):
    store = DummyStore()
    result_messages = [
        HumanMessage(
            content=[
                {"type": "text", "text": "describe"},
                {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
            ]
        ),
        AIMessage(content="image response"),
    ]
    graph = DummyGraph({"messages": result_messages})
    monkeypatch.setattr(http_conversation, "_graph", graph)
    monkeypatch.setattr(http_conversation, "_store", store)

    body = {
        "conversation_id": "conv-2",
        "input": [
            {"type": "text", "text": "describe"},
            {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
        ],
    }
    req = _make_request(body)
    resp = http_conversation.conversation_run(req)

    assert resp.status_code == 200
    assert json.loads(resp.get_body()) == {"output": "image response"}
    assert store.records["conv-2"] == result_messages


def test_conversation_run_requires_conversation_id(monkeypatch):
    store = DummyStore()
    monkeypatch.setattr(http_conversation, "_store", store)
    monkeypatch.setattr(http_conversation, "_graph", DummyGraph({"messages": []}))

    req = _make_request({"input": "hello"})
    resp = http_conversation.conversation_run(req)

    assert resp.status_code == 400
    assert b"conversation_id is required" in resp.get_body()


def test_conversation_run_isolated_histories(monkeypatch):
    store = DummyStore()
    store.records["alpha"] = [HumanMessage(content="a previous question")]
    store.records["beta"] = [HumanMessage(content="b previous question")]

    alpha_result = [
        HumanMessage(content="a previous question"),
        HumanMessage(content="alpha new"),
        AIMessage(content="alpha answer"),
    ]
    beta_result = [
        HumanMessage(content="b previous question"),
        HumanMessage(content="beta new"),
        AIMessage(content="beta answer"),
    ]

    class SwitchingGraph:
        def __init__(self):
            self.invocations = []

        def invoke(self, state):
            self.invocations.append(state)
            latest = state["messages"][-1].content
            return {"messages": alpha_result if str(latest).startswith("alpha") else beta_result}

    graph = SwitchingGraph()
    monkeypatch.setattr(http_conversation, "_graph", graph)
    monkeypatch.setattr(http_conversation, "_store", store)

    req_alpha = _make_request({"conversation_id": "alpha", "input": "alpha new"})
    req_beta = _make_request({"conversation_id": "beta", "input": "beta new"})

    resp_alpha = http_conversation.conversation_run(req_alpha)
    resp_beta = http_conversation.conversation_run(req_beta)

    assert resp_alpha.status_code == 200
    assert resp_beta.status_code == 200

    assert graph.invocations[0]["messages"][0].content == "a previous question"
    assert graph.invocations[1]["messages"][0].content == "b previous question"

    assert store.records["alpha"] == alpha_result
    assert store.records["beta"] == beta_result


def test_conversation_reset_returns_new_identifier(monkeypatch):
    store = DummyStore()
    store.records["conv-3"] = [HumanMessage(content="old question")]
    monkeypatch.setattr(http_conversation, "_store", store)
    monkeypatch.setattr(http_conversation, "_graph", DummyGraph({"messages": []}))
    monkeypatch.setattr(
        http_conversation,
        "uuid",
        SimpleNamespace(uuid4=lambda: uuid.UUID("00000000-0000-0000-0000-000000000123")),
    )

    req = func.HttpRequest(
        method="POST",
        url="/api/conversationReset",
        headers={"Content-Type": "application/json"},
        params={},
        route_params={},
        body=json.dumps({"conversation_id": "conv-3"}).encode(),
    )
    resp = http_conversation.conversation_reset(req)

    assert resp.status_code == 200
    assert store.records["conv-3"] == [HumanMessage(content="old question")]
    assert store.deleted == []
    assert json.loads(resp.get_body()) == {
        "status": "reset",
        "conversation_id": "00000000-0000-0000-0000-000000000123",
        "previous_conversation_id": "conv-3",
    }
