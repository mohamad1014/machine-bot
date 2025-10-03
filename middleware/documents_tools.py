from __future__ import annotations

"""Azure AI Search tools for docling research documents."""

import json
import os
from typing import Any, Callable, Sequence

try:  # pragma: no cover - optional dependency surface
    from langchain.tools import BaseTool
except Exception:  # pragma: no cover
    class BaseTool:  # type: ignore[too-many-ancestors]
        """Fallback BaseTool used when LangChain is unavailable."""

        name: str = ""
        description: str = ""

        def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - passthrough
            pass

        def run(self, *args, **kwargs):  # pragma: no cover - passthrough wrapper
            return self._run(*args, **kwargs)

        # pylint: disable=unused-argument
        def _run(self, *args, **kwargs):  # pragma: no cover - abstract placeholder
            raise NotImplementedError

        async def _arun(self, *args, **kwargs):  # pragma: no cover - async unsupported
            raise NotImplementedError

try:  # pragma: no cover - pydantic might not be installed in minimal envs
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover
    class BaseModel:  # type: ignore[too-many-ancestors]
        def __init__(self, **data: Any) -> None:
            for key, value in data.items():
                setattr(self, key, value)

    def Field(  # type: ignore[misc]
        default: Any = None,
        description: str = "",
        min_length: int | None = None,
    ) -> Any:
        return default

try:  # pragma: no cover - optional dependency
    import requests
except Exception:  # pragma: no cover - allow injection during tests
    requests = None  # type: ignore[assignment]


RequestCallable = Callable[[str, dict[str, str], dict[str, Any]], Any]


def _default_requester(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> Any:
    """Send a POST request to Azure AI Search using ``requests``."""

    if requests is None:  # pragma: no cover - executed only when dependency missing
        raise RuntimeError(
            "The 'requests' package is required to call Azure AI Search."
        )
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    return response


def _normalize_values(values: Sequence[str]) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _escape_single_quotes(value: str) -> str:
    return value.replace("'", "''")


def _collection_filter(field: str, values: Sequence[str]) -> str | None:
    normalized = _normalize_values(values)
    if not normalized:
        return None
    escaped = [
        _escape_single_quotes(item)
        for item in normalized
    ]
    joined = "|".join(escaped)
    return f"{field}/any(item: search.in(item, '{joined}', '|'))"


def _equal_any_filter(field: str, values: Sequence[str]) -> str | None:
    normalized = _normalize_values(values)
    if not normalized:
        return None
    comparisons = [f"{field} eq '{_escape_single_quotes(value)}'" for value in normalized]
    if len(comparisons) == 1:
        return comparisons[0]
    return "(" + " or ".join(comparisons) + ")"


class AzureSearchToolBase(BaseTool):
    """Base class with shared Azure AI Search plumbing."""

    api_version: str = "2023-11-01"
    endpoint: str | None = None
    api_key: str | None = None
    index_name: str | None = None

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        index_name: str | None = None,
        index_env_var: str | None = None,
        api_version: str | None = None,
        requester: RequestCallable | None = None,
    ) -> None:
        super().__init__()
        resolved_endpoint = endpoint or os.environ.get("AZURE_SEARCH_ENDPOINT")
        resolved_api_key = api_key or os.environ.get("AZURE_SEARCH_API_KEY")
        resolved_index = index_name
        if not resolved_index and index_env_var:
            resolved_index = os.environ.get(index_env_var)
        if not resolved_index:
            resolved_index = os.environ.get("AZURE_SEARCH_INDEX_NAME")
        resolved_api_version = (
            api_version
            or os.environ.get("AZURE_SEARCH_API_VERSION")
            or self.api_version
        )

        object.__setattr__(self, "endpoint", resolved_endpoint)
        object.__setattr__(self, "api_key", resolved_api_key)
        object.__setattr__(self, "index_name", resolved_index)
        object.__setattr__(self, "api_version", resolved_api_version)
        object.__setattr__(self, "_requester", requester or _default_requester)

        if not all([self.endpoint, self.api_key, self.index_name]):
            raise ValueError(
                "AzureSearchToolBase requires endpoint, api_key, and index_name"
            )

    # ------------------------------------------------------------------
    def _build_search_url(self) -> str:
        base = self.endpoint.rstrip("/")
        return (
            f"{base}/indexes/{self.index_name}/docs/search"
            f"?api-version={self.api_version}"
        )

    # ------------------------------------------------------------------
    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = self._build_search_url()
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key or "",
        }
        response = self._requester(url, headers, payload)
        return self._parse_response(response)

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_response(response: Any) -> dict[str, Any]:
        if isinstance(response, tuple) and len(response) == 2:
            status_code, body = response
            if status_code >= 400:
                raise RuntimeError(
                    f"Azure AI Search error ({status_code}): {body}"
                )
            if isinstance(body, dict):
                return body
            if isinstance(body, str):
                try:
                    return json.loads(body)
                except json.JSONDecodeError as exc:  # pragma: no cover - defensive
                    raise RuntimeError(
                        "Failed to parse Azure AI Search response"
                    ) from exc
            raise RuntimeError("Unsupported response body type from Azure AI Search")

        status_code = getattr(response, "status_code", 200)
        if status_code >= 400:
            text = getattr(response, "text", "") or "<empty body>"
            raise RuntimeError(
                f"Azure AI Search error ({status_code}): {text}"
            )
        if hasattr(response, "json"):
            return response.json()
        if isinstance(response, dict):
            return response
        raise RuntimeError("Unexpected response type from Azure AI Search")


class DoclingDocumentSearchInput(BaseModel):
    """Input schema for :class:`DoclingDocumentSearchTool`."""

    query: str = Field(..., description="Full-text query to execute against the documents index.")
    tags: list[str] = Field(
        default_factory=list,
        description="Optional OR filter over the `tags` collection.",
    )
    industry_tags: list[str] = Field(
        default_factory=list,
        description="Optional OR filter over the `industry_tags` collection.",
    )
    application_tags: list[str] = Field(
        default_factory=list,
        description="Optional OR filter over the `application_tags` collection.",
    )
    document_types: list[str] = Field(
        default_factory=list,
        description="Optional OR filter over the `document_types` collection.",
    )
    source_urls: list[str] = Field(
        default_factory=list,
        description="Optional OR filter over exact `source_url` matches.",
    )
    min_mean_score: float | None = Field(
        default=None,
        description="Lower bound for the `mean_score` field.",
    )
    min_low_score: float | None = Field(
        default=None,
        description="Lower bound for the `low_score` field.",
    )
    min_chunk_count: int | None = Field(
        default=None,
        description="Lower bound for the `chunk_count` field.",
    )
    max_chunk_count: int | None = Field(
        default=None,
        description="Upper bound for the `chunk_count` field.",
    )
    top: int = Field(
        default=5,
        description="Maximum number of documents to return.",
    )
    semantic_configuration: str = Field(
        default="default",
        description="Semantic configuration registered on the index.",
    )
    query_language: str = Field(
        default="en-us",
        description="Language hint for semantic ranking.",
    )
    search_fields: list[str] = Field(
        default_factory=lambda: ["title", "abstract", "content"],
        description="Fields to target with the full-text query.",
    )


class DoclingDocumentSearchTool(AzureSearchToolBase):
    """Query docling documents and return titles, abstracts, and identifiers."""

    name: str = "docling_documents_search"
    description: str = (
        "Search the docling documents Azure AI Search index. Provide a natural language"
        " query and optional tag filters. The tool returns only the document_id, title,"
        " and abstract fields along with the JSON payload that was sent to the service."
    )
    args_schema: type[BaseModel] = DoclingDocumentSearchInput

    def __init__(
        self,
        *,
        search_fields: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        object.__setattr__(
            self,
            "search_fields",
            list(search_fields or ["title", "abstract", "content"]),
        )

    def run(self, *args: Any, **kwargs: Any) -> str:  # noqa: D401 - wrapper
        data: DoclingDocumentSearchInput
        if args:
            first = args[0]
            if isinstance(first, DoclingDocumentSearchInput):
                data = first
            elif isinstance(first, dict):
                data = DoclingDocumentSearchInput(**first)
            elif isinstance(first, str):
                data = DoclingDocumentSearchInput(query=first)
            else:
                raise TypeError(
                    "Unsupported positional argument for docling_documents_search"
                )
        elif "tool_input" in kwargs:
            tool_input = kwargs["tool_input"]
            if isinstance(tool_input, DoclingDocumentSearchInput):
                data = tool_input
            elif isinstance(tool_input, dict):
                data = DoclingDocumentSearchInput(**tool_input)
            elif isinstance(tool_input, str):
                data = DoclingDocumentSearchInput(query=tool_input)
            else:
                raise TypeError(
                    "Unsupported tool_input for docling_documents_search"
                )
        else:
            data = DoclingDocumentSearchInput(**kwargs)
        return self._run(data)

    # pylint: disable=unused-argument
    def _run(self, data: DoclingDocumentSearchInput) -> str:  # type: ignore[override]
        payload = self._build_payload(data)
        response = self._post(payload)
        results = [
            {
                "document_id": item.get("document_id"),
                "title": item.get("title"),
                "abstract": item.get("abstract"),
            }
            for item in response.get("value", [])
        ]
        return json.dumps({"request": payload, "results": results}, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    def _build_payload(self, data: DoclingDocumentSearchInput) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "search": data.query,
            "top": data.top,
            "queryType": "semantic",
            "semanticConfiguration": data.semantic_configuration,
            "queryLanguage": data.query_language,
            "select": "document_id,title,abstract",
        }
        search_fields = _normalize_values(data.search_fields or self.search_fields)
        if search_fields:
            payload["searchFields"] = ",".join(search_fields)

        filters: list[str] = []
        for field_name, values in [
            ("tags", data.tags),
            ("industry_tags", data.industry_tags),
            ("application_tags", data.application_tags),
            ("document_types", data.document_types),
        ]:
            clause = _collection_filter(field_name, values)
            if clause:
                filters.append(clause)

        source_filter = _equal_any_filter("source_url", data.source_urls)
        if source_filter:
            filters.append(source_filter)

        if data.min_mean_score is not None:
            filters.append(f"mean_score ge {data.min_mean_score}")
        if data.min_low_score is not None:
            filters.append(f"low_score ge {data.min_low_score}")
        if data.min_chunk_count is not None:
            filters.append(f"chunk_count ge {data.min_chunk_count}")
        if data.max_chunk_count is not None:
            filters.append(f"chunk_count le {data.max_chunk_count}")

        if filters:
            payload["filter"] = " and ".join(filters)

        return payload


class DoclingDocumentContentInput(BaseModel):
    """Input schema for :class:`DoclingDocumentContentTool`."""

    document_ids: list[str] = Field(
        ..., description="List of document identifiers to retrieve.", min_length=1
    )
    confirm: bool = Field(
        default=False,
        description="Set to true after the user approves retrieving full content.",
    )
    metadata_fields: list[str] = Field(
        default_factory=list,
        description="Optional metadata fields to include alongside the content.",
    )


class DoclingDocumentContentTool(AzureSearchToolBase):
    """Retrieve document content after explicit user confirmation."""

    name: str = "docling_documents_content"
    description: str = (
        "Fetch the full `content` for approved docling documents. Always call the"
        " tool first with `confirm: false` (the default) to preview document ids,"
        " then present the preview to the user. Only after receiving approval should"
        " you call it again with `confirm: true` to download the full content for"
        " analysis."
    )
    args_schema: type[BaseModel] = DoclingDocumentContentInput

    def __init__(
        self,
        *,
        metadata_fields: Sequence[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        object.__setattr__(self, "metadata_fields", list(metadata_fields or []))

    def run(self, *args: Any, **kwargs: Any) -> str:  # noqa: D401 - wrapper
        data: DoclingDocumentContentInput
        if args:
            first = args[0]
            if isinstance(first, DoclingDocumentContentInput):
                data = first
            elif isinstance(first, dict):
                data = DoclingDocumentContentInput(**first)
            else:
                raise TypeError(
                    "Unsupported positional argument for docling_documents_content"
                )
        elif "tool_input" in kwargs:
            tool_input = kwargs["tool_input"]
            if isinstance(tool_input, DoclingDocumentContentInput):
                data = tool_input
            elif isinstance(tool_input, dict):
                data = DoclingDocumentContentInput(**tool_input)
            else:
                raise TypeError(
                    "Unsupported tool_input for docling_documents_content"
                )
        else:
            data = DoclingDocumentContentInput(**kwargs)
        return self._run(data)

    # pylint: disable=unused-argument
    def _run(self, data: DoclingDocumentContentInput) -> str:  # type: ignore[override]
        doc_ids = _normalize_values(data.document_ids)
        if not doc_ids:
            raise ValueError("At least one document_id must be provided.")

        combined_metadata = list(dict.fromkeys(self.metadata_fields + data.metadata_fields))

        if not data.confirm:
            preview = [{"document_id": identifier} for identifier in doc_ids]
            return json.dumps(
                {
                    "status": "preview",
                    "message": (
                        "Review the listed document identifiers with the user."
                        " Call the tool again with `confirm: true` only after the"
                        " user approves retrieving full content."
                    ),
                    "documents": preview,
                },
                indent=2,
                ensure_ascii=False,
            )

        filter_clause = _equal_any_filter("document_id", doc_ids)
        payload: dict[str, Any] = {
            "search": "*",
            "top": len(doc_ids),
            "select": ",".join(
                dict.fromkeys(["document_id", "title", "content", *combined_metadata])
            ),
        }
        if filter_clause:
            payload["filter"] = filter_clause

        response = self._post(payload)
        documents: list[dict[str, Any]] = []
        for item in response.get("value", []):
            entry: dict[str, Any] = {
                "document_id": item.get("document_id"),
                "title": item.get("title"),
                "content": item.get("content"),
            }
            for field in combined_metadata:
                entry[field] = item.get(field)
            documents.append(entry)

        return json.dumps(
            {
                "status": "complete",
                "documents": documents,
            },
            indent=2,
            ensure_ascii=False,
        )


__all__ = [
    "AzureSearchToolBase",
    "DoclingDocumentSearchInput",
    "DoclingDocumentSearchTool",
    "DoclingDocumentContentInput",
    "DoclingDocumentContentTool",
]
