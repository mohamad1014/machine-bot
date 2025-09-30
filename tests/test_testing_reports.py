from __future__ import annotations

import types

import pytest

from middleware import testing_reports


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
        FakeDocument(
            page_content="Bearing endurance test report", metadata={"source": "reports/endurance"}
        ),
        FakeDocument(
            page_content="Vibration anomaly analysis",
            metadata={"source": "reports/vibration", "test_rig": "Rig-7"},
        ),
    ]
    tool = testing_reports.TestingReportsSearchTool(retriever=FakeRetriever(docs))

    output = tool.run(query="endurance performance")

    assert "Bearing endurance test report" in output
    assert "source: reports/endurance" in output
    assert "Vibration anomaly analysis" in output
    assert "test_rig: Rig-7" in output


def test_tool_missing_configuration(monkeypatch):
    monkeypatch.delenv("AZURE_SEARCH_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_SEARCH_INDEX_NAME", raising=False)
    tool = testing_reports.TestingReportsSearchTool(retriever=None)

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
    tool = testing_reports.TestingReportsSearchTool(retriever=retriever)

    tool.run({"query": "anything", "top_k": 1})

    assert retriever.top_k == 1
    assert retriever.received_queries == ["anything"]


def test_tool_supports_index_override():
    docs = [FakeDocument(page_content="Metallurgy report", metadata={})]
    retriever = FakeRetriever(docs)
    retriever.index_name = "baseline-index"
    tool = testing_reports.TestingReportsSearchTool(retriever=retriever)

    tool.run({"query": "metallurgy", "index_name": "metallurgy-index"})

    assert getattr(retriever, "index_name", None) == "metallurgy-index"
