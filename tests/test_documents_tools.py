from __future__ import annotations

import json

import pytest

from middleware.documents_tools import (
    DoclingDocumentContentInput,
    DoclingDocumentContentTool,
    DoclingDocumentSearchInput,
    DoclingDocumentSearchTool,
)


class FakeRequester:
    """Callable stub that records requests and returns canned responses."""

    def __init__(self, response: dict[str, object]) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, str], dict[str, object]]] = []

    def __call__(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object],
    ) -> tuple[int, dict[str, object]]:
        self.calls.append((url, headers, payload))
        return 200, self.response


@pytest.fixture()
def azure_search_kwargs() -> dict[str, str]:
    return {
        "endpoint": "https://example.search.windows.net",
        "api_key": "dummy-key",
        "index_name": "docling-index",
    }


def test_docling_document_search_builds_payload_and_trims_results(azure_search_kwargs):
    requester = FakeRequester(
        {
            "value": [
                {
                    "document_id": "doc-1",
                    "title": "Bearing fatigue overview",
                    "abstract": "Summary of accelerated life testing.",
                    "content": "This field should not be returned.",
                }
            ],
            "@odata.count": 1,
        }
    )
    tool = DoclingDocumentSearchTool(
        requester=requester,
        search_fields=["title", "abstract"],
        **azure_search_kwargs,
    )

    input_data = DoclingDocumentSearchInput(
        query="fatigue testing",
        tags=["bearing", "life"],
    )
    result = tool.run(input_data)
    payload = requester.calls[-1][2]

    assert payload["select"] == "document_id,title,abstract"
    assert "tags/any" in payload["filter"]
    content = result.content if hasattr(result, "content") else result
    parsed = json.loads(content)
    assert parsed["request"]["search"] == "fatigue testing"
    assert parsed["@odata.count"] == 1
    assert parsed["results"] == [
        {
            "document_id": "doc-1",
            "title": "Bearing fatigue overview",
            "abstract": "Summary of accelerated life testing.",
        }
    ]


def test_docling_document_search_accepts_string_input(azure_search_kwargs):
    requester = FakeRequester({"value": [], "@odata.count": 0})
    tool = DoclingDocumentSearchTool(requester=requester, **azure_search_kwargs)

    result = tool.run("seal failures")
    payload = requester.calls[-1][2]

    assert payload["search"] == "seal failures"
    content = result.content if hasattr(result, "content") else result
    parsed = json.loads(content)
    assert parsed["results"] == []
    assert parsed["@odata.count"] == 0


class FakeCosmosContainer:
    """In-memory container stub used for content tool tests."""

    def __init__(self, documents: list[dict[str, object]]) -> None:
        self._documents = list(documents)
        self.queries: list[tuple[str, list[dict[str, object]], bool]] = []

    def query_items(
        self,
        *,
        query: str,
        parameters: list[dict[str, object]],
        enable_cross_partition_query: bool,
    ):
        self.queries.append((query, parameters, enable_cross_partition_query))
        requested = {
            str(param["value"])
            for param in parameters
            if isinstance(param.get("value"), str)
        }
        for document in self._documents:
            identifier = document.get("id")
            if isinstance(identifier, str) and identifier in requested:
                yield document


def test_docling_document_content_fetches_from_cosmos():
    container = FakeCosmosContainer(
        [
            {"id": "doc-7", "title": "Rotor balance trial", "content": "Detailed procedures"},
            {"id": "doc-9", "content": "Other"},
        ]
    )
    tool = DoclingDocumentContentTool(container_client=container)

    result = tool.run({"document_ids": ["doc-7", "missing"]})
    content = result.content if hasattr(result, "content") else result
    payload = json.loads(content)

    assert payload["documents"][0]["document_id"] == "doc-7"
    assert payload["documents"][0]["title"] == "Rotor balance trial"
    assert payload["missing_document_ids"] == ["missing"]

    query, parameters, cross_partition = container.queries[-1]
    assert "c.id IN" in query
    assert cross_partition is True
    assert {param["value"] for param in parameters} == {"doc-7", "missing"}


def test_docling_document_content_rejects_empty_identifiers():
    tool = DoclingDocumentContentTool(container_client=FakeCosmosContainer([]))

    with pytest.raises(ValueError):
        tool.run(DoclingDocumentContentInput(document_ids=[]))
