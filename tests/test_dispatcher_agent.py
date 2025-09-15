"""Basic tests for dispatcher and maintenance agents."""
from __future__ import annotations

import agents.vanilla_agent as vanilla_agent
from agents.dispatcher_agent import DispatcherAgent
from agents.maintenance_agent import MaintenanceAgent
from langchain_core.messages import AIMessage


class FakeListChatModel:
    def __init__(self, responses):
        self._responses = list(responses)

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):  # pragma: no cover
        return self._responses.pop(0)


def test_dispatcher_agent_basic_response(monkeypatch):
    model = FakeListChatModel([AIMessage(content="dispatch ok")])
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: model)
    agent = DispatcherAgent()
    result = agent.invoke({"input": "hello"})
    assert result["messages"][-1].content == "dispatch ok"


def test_maintenance_agent_basic_response(monkeypatch):
    model = FakeListChatModel([AIMessage(content="maintenance ok")])
    monkeypatch.setattr(vanilla_agent, "AzureChatOpenAI", lambda **_: model)
    agent = MaintenanceAgent()
    result = agent.invoke({"input": "check"})
    assert result["messages"][-1].content == "maintenance ok"
