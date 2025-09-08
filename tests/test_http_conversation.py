import json
import pytest

func = pytest.importorskip("azure.functions")

from functions.http_conversation import conversation_run


class DummyAgent:
    """Simple agent that returns a pre-defined result regardless of input."""

    def __init__(self, result: dict):
        self._result = result

    # Support multiple calling styles
    def run(self, *_, **__):
        return self._result

    def respond(self, *_, **__):
        return self._result

    def __call__(self, *_, **__):
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
    expected = {
        "id": "1",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "text response"}],
    }
    agent = DummyAgent(expected)
    # Patch whichever creation path is used by the function
    monkeypatch.setattr(
        "functions.http_conversation.create_manual_agent",
        lambda: agent,
        raising=False,
    )
    monkeypatch.setattr(
        "functions.http_conversation.agent",
        agent,
        raising=False,
    )
    req = _make_request({"input": "hello"})
    resp = conversation_run(req)
    assert resp.status_code == 200
    assert json.loads(resp.get_body()) == expected


def test_conversation_run_multimodal(monkeypatch):
    expected = {
        "id": "2",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": "image response"}],
    }
    agent = DummyAgent(expected)
    monkeypatch.setattr(
        "functions.http_conversation.create_manual_agent",
        lambda: agent,
        raising=False,
    )
    monkeypatch.setattr(
        "functions.http_conversation.agent",
        agent,
        raising=False,
    )
    req = _make_request(
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": "describe"},
                        {"type": "input_image", "image_url": "https://example.com/cat.png"},
                    ],
                }
            ]
        }
    )
    resp = conversation_run(req)
    assert resp.status_code == 200
    assert json.loads(resp.get_body()) == expected
