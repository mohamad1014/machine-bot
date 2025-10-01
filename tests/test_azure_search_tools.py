from __future__ import annotations

import types

import pytest

from middleware import azure_search_tools


class FakeRetriever:
    def __init__(self, documents):
        self._documents = list(documents)
        self.received_queries: list[str] = []
        self.top_k = len(self._documents)

    def get_relevant_documents(self, query):
        self.received_queries.append(query)
        return list(self._documents)


class FakeDocument(types.SimpleNamespace):
    pass


def test_tool_formats_results(monkeypatch):
    docs = [
        FakeDocument(page_content="Pump calibration guide", metadata={"source": "kb1"}),
        FakeDocument(page_content="Replace filter", metadata={"source": "kb2", "score": 0.42}),
    ]
    tool = azure_search_tools.AzureAISearchTool(retriever=FakeRetriever(docs))

    output = tool.run(query="calibration steps")

    assert "Pump calibration guide" in output
    assert "source: kb1" in output
    assert "Replace filter" in output
    assert "score: 0.42" in output


def test_tool_missing_configuration(monkeypatch):
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_INDEX_NAME", raising=False)
    tool = azure_search_tools.AzureAISearchTool(retriever=None)

    with pytest.raises(RuntimeError) as exc_info:
        tool.run(query="status")

    assert "not configured" in str(exc_info.value)


def test_tool_respects_top_k(monkeypatch):
    docs = [
        FakeDocument(page_content="Result 1", metadata={}),
        FakeDocument(page_content="Result 2", metadata={}),
        FakeDocument(page_content="Result 3", metadata={}),
    ]
    retriever = FakeRetriever(docs)
    tool = azure_search_tools.AzureAISearchTool(retriever=retriever)

    tool.run({"query": "anything", "top_k": 1})

    assert retriever.top_k == 1
    assert retriever.received_queries == ["anything"]
