from __future__ import annotations

"""Tools for retrieving testing reports about physical bearing trials."""

import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional

try:  # pragma: no cover - optional dependency surface
    from langchain.tools import BaseTool
except Exception:  # pragma: no cover
    class BaseTool:  # type: ignore[too-many-ancestors]
        """Fallback BaseTool used when LangChain is unavailable."""

        name: str = ""
        description: str = ""

        def __init__(self, *args, **kwargs) -> None:  # noqa: D401
            pass

        def run(self, *args, **kwargs):  # pragma: no cover - passthrough wrapper
            return self._run(*args, **kwargs)

        # pylint: disable=unused-argument
        def _run(self, *args, **kwargs):  # pragma: no cover - abstract placeholder
            raise NotImplementedError

        async def _arun(self, *args, **kwargs):  # pragma: no cover - async unsupported
            raise NotImplementedError

try:  # pragma: no cover - pydantic might not be installed in minimal envs
    from pydantic import BaseModel, Field, PrivateAttr
except Exception:  # pragma: no cover
    class BaseModel:  # type: ignore[too-many-ancestors]
        def __init__(self, **data: Any) -> None:
            for key, value in data.items():
                setattr(self, key, value)

    def Field(default: Any, description: str = "") -> Any:
        return default

    def PrivateAttr(default: Any = None) -> Any:
        return default

from langchain_core.tools import tool


TOOL_DESCRIPTION = (
    "Search Azure AI Search indexes that store physical bearing testing reports"
    " and diagnostics."
)


class TestingReportsToolInput(BaseModel):
    """Input schema for :class:`TestingReportsSearchTool`."""

    query: str = Field(..., description="Natural language search query.")
    top_k: Optional[int] = Field(
        default=None,
        description="Optional limit for the number of results to return.",
    )
    index_name: Optional[str] = Field(
        default=None,
        description=(
            "Optional override for the Azure AI Search index name. Useful for"
            " switching between report collections."
        ),
    )


@dataclass
class _RenderableDocument:
    """Lightweight container for formatted document output."""

    content: str
    metadata: dict[str, Any]

    def format(self) -> str:
        """Format a document for presentation to the model."""

        meta_lines = [f"{key}: {value}" for key, value in self.metadata.items()]
        meta_block = f"\nMetadata: {', '.join(meta_lines)}" if meta_lines else ""
        return f"{self.content}{meta_block}"


class TestingReportsSearchTool(BaseTool):
    """LangChain tool that queries Azure AI Search for bearing testing reports."""

    name: str = "testing_reports_search"
    description: str = TOOL_DESCRIPTION
    args_schema: type[BaseModel] = TestingReportsToolInput

    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    index_name: Optional[str] = None
    content_key: str = "content"
    top_k: int = 5
    vector_field: Optional[str] = None
    index_env_var: Optional[str] = None
    api_version: str = "2023-11-01"
    _retriever: Any = PrivateAttr(default=None)

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        index_env_var: Optional[str] = None,
        content_key: Optional[str] = None,
        top_k: Optional[int] = None,
        vector_field: Optional[str] = None,
        retriever: Any | None = None,
        api_version: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.endpoint = endpoint or os.environ.get("AZURE_SEARCH_ENDPOINT")
        self.api_key = api_key or os.environ.get("AZURE_SEARCH_API_KEY")
        self.index_env_var = index_env_var
        env_index = os.environ.get(index_env_var) if index_env_var else None
        default_env_index = os.environ.get("AZURE_SEARCH_INDEX_NAME")
        self.index_name = index_name or env_index or default_env_index
        self.content_key = (
            content_key
            or os.environ.get("AZURE_SEARCH_CONTENT_KEY")
            or "content"
        )
        raw_top_k = top_k or os.environ.get("AZURE_SEARCH_TOP_K")
        try:
            self.top_k = int(raw_top_k) if raw_top_k is not None else 5
        except (TypeError, ValueError):  # pragma: no cover - defensive parsing
            self.top_k = 5
        self.vector_field = vector_field or os.environ.get("AZURE_SEARCH_VECTOR_FIELD")
        self.api_version = (
            api_version
            or os.environ.get("AZURE_SEARCH_API_VERSION")
            or "2023-11-01"
        )
        if retriever is not None:
            self._retriever = retriever
            if self.vector_field and hasattr(self._retriever, "vector_field"):
                try:
                    setattr(self._retriever, "vector_field", self.vector_field)
                except Exception:  # pragma: no cover - defensive
                    pass
        elif all([self.endpoint, self.api_key, self.index_name]):
            self._retriever = self._build_retriever()
        else:
            self._retriever = None

    # ------------------------------------------------------------------
    def _build_retriever(self, *, index_name: Optional[str] = None) -> Any | None:
        """Instantiate a LangChain retriever if dependencies are available."""

        try:  # pragma: no cover - optional dependency surface
            from langchain_community.retrievers import AzureAISearchRetriever
        except Exception:
            return None
        selected_index = index_name or self.index_name
        if not all([self.endpoint, self.api_key, selected_index]):
            return None
        kwargs: dict[str, Any] = {
            "service_name": self.endpoint,
            "api_key": self.api_key or "",
            "index_name": selected_index,
            "content_key": self.content_key,
            "top_k": self.top_k,
            "api_version": self.api_version,
        }
        try:
            retriever = AzureAISearchRetriever(**kwargs)
            if self.vector_field and hasattr(retriever, "vector_field"):
                setattr(retriever, "vector_field", self.vector_field)
            return retriever
        except Exception:  # pragma: no cover - avoid crashing on SDK errors
            return None

    # ------------------------------------------------------------------
    def run(self, *args: Any, **kwargs: Any) -> str:  # noqa: D401 - wrapper
        """Support multiple invocation styles for compatibility with LangChain."""

        query: Optional[str] = None
        top_k: Optional[int] = None
        index_name: Optional[str] = None
        if args:
            first_arg = args[0]
            if isinstance(first_arg, str):
                query = first_arg
            elif isinstance(first_arg, dict):
                query = first_arg.get("query")
                top_k = first_arg.get("top_k")
                index_name = first_arg.get("index_name")
            else:
                query = getattr(first_arg, "query", None)
                top_k = getattr(first_arg, "top_k", None)
                index_name = getattr(first_arg, "index_name", None)
        if "tool_input" in kwargs:
            tool_input = kwargs["tool_input"]
            if isinstance(tool_input, dict):
                query = tool_input.get("query") or query
                top_k = tool_input.get("top_k") if top_k is None else top_k
                index_name = (
                    tool_input.get("index_name")
                    if index_name is None
                    else index_name
                )
            else:
                query = getattr(tool_input, "query", query)
                top_k = getattr(tool_input, "top_k", top_k)
                index_name = getattr(tool_input, "index_name", index_name)
        query = kwargs.get("query", query)
        top_k = kwargs.get("top_k", top_k)
        index_name = kwargs.get("index_name", index_name)
        if query is None:
            raise TypeError("Missing required argument 'query'")
        return self._run(query=query, top_k=top_k, index_name=index_name)

    # pylint: disable=unused-argument
    def _run(
        self, query: str, top_k: Optional[int] = None, index_name: Optional[str] = None
    ) -> str:  # type: ignore[override]
        retriever = self._ensure_retriever(index_name=index_name)
        self._configure_top_k(retriever, top_k)
        documents = retriever.get_relevant_documents(query)
        formatted = self._format_documents(documents)
        if not formatted:
            return "No relevant testing reports were found in Azure AI Search."
        return "\n\n".join(doc.format() for doc in formatted)

    async def _arun(
        self, query: str, top_k: Optional[int] = None, index_name: Optional[str] = None
    ) -> str:  # type: ignore[override]
        raise NotImplementedError(
            "TestingReportsSearchTool does not support async execution"
        )

    # ------------------------------------------------------------------
    def _ensure_retriever(self, *, index_name: Optional[str]) -> Any:
        if self._retriever is None:
            if index_name is not None:
                self.index_name = index_name
            self._retriever = self._build_retriever(index_name=self.index_name)
        if self._retriever is None:
            resolved_index = index_name or self.index_name
            index_identifier = self.index_env_var or "AZURE_SEARCH_INDEX_NAME"
            missing = [
                name
                for name, value in (
                    ("AZURE_SEARCH_ENDPOINT", self.endpoint),
                    ("AZURE_SEARCH_API_KEY", self.api_key),
                    (index_identifier, resolved_index),
                )
                if not value
            ]
            resolved_repr = (
                "TestingReportsSearchTool("
                f"endpoint={self.endpoint!r}, "
                f"api_key={self.api_key!r}, "
                f"index_name={resolved_index!r}, "
                f"index_env_var={(self.index_env_var or '')!r})"
            )
            detail = f" Missing settings: {', '.join(missing)}" if missing else ""
            raise RuntimeError(
                "Azure AI Search retriever is not configured for testing reports. "
                f"Resolved configuration: {resolved_repr}.{detail}"
            )
        if index_name and hasattr(self._retriever, "index_name"):
            try:
                setattr(self._retriever, "index_name", index_name)
            except Exception:  # pragma: no cover - best effort
                pass
        return self._retriever

    @staticmethod
    def _configure_top_k(retriever: Any, top_k: Optional[int]) -> None:
        if top_k is None:
            return
        for attr in ("top_k", "k"):
            if hasattr(retriever, attr):
                try:
                    setattr(retriever, attr, top_k)
                    return
                except Exception:  # pragma: no cover - best effort
                    continue

    @staticmethod
    def _format_documents(documents: Iterable[Any]) -> list[_RenderableDocument]:
        formatted: list[_RenderableDocument] = []
        for doc in documents:
            if doc is None:  # pragma: no cover - guard for defensive callers
                continue
            content = getattr(doc, "page_content", None) or str(doc)
            metadata = getattr(doc, "metadata", None)
            if not isinstance(metadata, dict):
                metadata = {}
            formatted.append(_RenderableDocument(content=content, metadata=metadata))
        return formatted


@tool("testing_reports_search", description=TOOL_DESCRIPTION)
def testing_reports_search(
    query: str, top_k: Optional[int] = None, index_name: Optional[str] = None
) -> str:
    """Tool entry-point that instantiates :class:`TestingReportsSearchTool`."""

    return TestingReportsSearchTool().run(
        query=query, top_k=top_k, index_name=index_name
    )

