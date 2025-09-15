"""Tests for the HTTP conversation Azure Function."""
from __future__ import annotations

import json

import azure.functions as func
from langchain_core.messages import AIMessage, HumanMessage

from functions import http_conversation
from agents import VanillaAgent


class DummyGraph:
    def __init__(self, result):
        self._result = result

    def invoke(self, state):  # pragma: no cover - simple passthrough
        return self._result


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
    result = {
        "messages": [HumanMessage(content="hello"), AIMessage(content="text response")]
    }
    monkeypatch.setattr(http_conversation, "_graph", DummyGraph(result))
    VanillaAgent.MEMORY = []
    req = _make_request({"input": "hello"})
    resp = http_conversation.conversation_run(req)
    assert resp.status_code == 200
    assert json.loads(resp.get_body()) == {"output": "text response"}


def test_conversation_run_multimodal(monkeypatch):
    result = {
        "messages": [
            HumanMessage(
                content=[
                    {"type": "text", "text": "describe"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/cat.png"},
                    },
                ]
            ),
            AIMessage(content="image response"),
        ]
    }
    monkeypatch.setattr(http_conversation, "_graph", DummyGraph(result))
    VanillaAgent.MEMORY = []
    body = {
        "input": [
            {"type": "text", "text": "describe"},
            {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
        ]
    }
    req = _make_request(body)
    resp = http_conversation.conversation_run(req)
    assert resp.status_code == 200
    assert json.loads(resp.get_body()) == {"output": "image response"}
