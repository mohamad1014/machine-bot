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
            ]
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
        min_mean_score=0.5,
        source_urls=["https://contoso"],
    )
    result = tool.run(input_data)
    payload = requester.calls[-1][2]

    assert payload["select"] == "document_id,title,abstract"
    assert "tags/any" in payload["filter"]
    assert "mean_score ge 0.5" in payload["filter"]
    assert "source_url eq 'https://contoso'" in payload["filter"]

    parsed = json.loads(result)
    assert parsed["request"]["search"] == "fatigue testing"
    assert parsed["results"] == [
        {
            "document_id": "doc-1",
            "title": "Bearing fatigue overview",
            "abstract": "Summary of accelerated life testing.",
        }
    ]


def test_docling_document_search_accepts_string_input(azure_search_kwargs):
    requester = FakeRequester({"value": []})
    tool = DoclingDocumentSearchTool(requester=requester, **azure_search_kwargs)

    result = tool.run("seal failures")
    payload = requester.calls[-1][2]

    assert payload["search"] == "seal failures"
    assert json.loads(result)["results"] == []


def test_docling_document_content_requires_confirmation(azure_search_kwargs):
    tool = DoclingDocumentContentTool(requester=FakeRequester({}), **azure_search_kwargs)

    preview = tool.run({"document_ids": ["doc-7", "doc-9"]})
    preview_payload = json.loads(preview)

    assert preview_payload["status"] == "preview"
    assert preview_payload["documents"] == [
        {"document_id": "doc-7"},
        {"document_id": "doc-9"},
    ]


def test_docling_document_content_fetches_after_confirmation(azure_search_kwargs):
    requester = FakeRequester(
        {
            "value": [
                {
                    "document_id": "doc-7",
                    "title": "Rotor balance trial",
                    "content": "Detailed procedures",
                    "abstract": "Rotor work",
                    "tags": ["rotor"],
                }
            ]
        }
    )
    tool = DoclingDocumentContentTool(
        requester=requester,
        metadata_fields=["abstract", "tags"],
        **azure_search_kwargs,
    )

    result = tool.run(
        DoclingDocumentContentInput(
            document_ids=["doc-7"],
            confirm=True,
        )
    )
    payload = requester.calls[-1][2]

    assert payload["select"] == "document_id,title,content,abstract,tags"
    assert "document_id eq 'doc-7'" in payload["filter"]

    parsed = json.loads(result)
    assert parsed["status"] == "complete"
    assert parsed["documents"][0]["content"] == "Detailed procedures"
    assert parsed["documents"][0]["abstract"] == "Rotor work"


def test_docling_document_content_rejects_empty_identifiers(azure_search_kwargs):
    tool = DoclingDocumentContentTool(requester=FakeRequester({}), **azure_search_kwargs)

    with pytest.raises(ValueError):
        tool.run(DoclingDocumentContentInput(document_ids=[], confirm=True))
