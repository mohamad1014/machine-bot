from __future__ import annotations

"""Tools for retrieving data from Azure AI Search."""

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

_MISSING = object()
_RETRIEVER_CLS: Any = _MISSING


def _get_retriever_cls() -> Any | None:
    """Dynamically import the Azure retriever only when required."""

    global _RETRIEVER_CLS  # noqa: PLW0603 - cache for repeated calls
    if _RETRIEVER_CLS is _MISSING:
        try:  # pragma: no cover - optional dependency surface
            from langchain_community.retrievers import AzureCognitiveSearchRetriever
        except Exception:
            _RETRIEVER_CLS = None
        else:
            _RETRIEVER_CLS = AzureCognitiveSearchRetriever
    return None if _RETRIEVER_CLS is None else _RETRIEVER_CLS

from langchain_core.tools import tool


TOOL_DESCRIPTION = "Search the Azure AI Search index for relevant machine information."


class AzureAISearchToolInput(BaseModel):
    """Input schema for :class:`AzureAISearchTool`."""

    query: str = Field(..., description="Natural language search query.")
    top_k: Optional[int] = Field(
        default=None,
        description="Optional limit for the number of results to return.",
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


class AzureAISearchTool(BaseTool):
    """LangChain tool that queries Azure AI Search and formats results."""

    name: str = "azure_ai_search"
    description: str = TOOL_DESCRIPTION
    args_schema: type[BaseModel] = AzureAISearchToolInput

    endpoint: Optional[str] = None
    api_key: Optional[str] = None
    index_name: Optional[str] = None
    content_key: str = "content"
    top_k: int = 5
    vector_field: Optional[str] = None
    _retriever: Any = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        content_key: Optional[str] = None,
        top_k: Optional[int] = None,
        vector_field: Optional[str] = None,
        retriever: Any | None = None,
    ) -> None:
        super().__init__()
        self.endpoint = endpoint or os.environ.get("AZURE_SEARCH_ENDPOINT")
        self.api_key = api_key or os.environ.get("AZURE_SEARCH_API_KEY")
        self.index_name = index_name or os.environ.get("AZURE_SEARCH_INDEX_NAME")
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
        if retriever is not None:
            self._retriever = retriever
        elif all([self.endpoint, self.api_key, self.index_name]):
            self._retriever = self._build_retriever()
        else:
            self._retriever = None

    # ------------------------------------------------------------------
    def _build_retriever(self) -> Any | None:
        """Instantiate a LangChain retriever if dependencies are available."""

        retriever_cls = _get_retriever_cls()
        if retriever_cls is None:
            return None
        if not all([self.endpoint, self.api_key, self.index_name]):
            return None
        try:
            retriever = retriever_cls(
                endpoint=self.endpoint,
                api_key=self.api_key,
                index_name=self.index_name,
                content_key=self.content_key,
                top_k=self.top_k,
            )
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
        if args:
            first_arg = args[0]
            if isinstance(first_arg, str):
                query = first_arg
            elif isinstance(first_arg, dict):
                query = first_arg.get("query")
                top_k = first_arg.get("top_k")
            else:
                query = getattr(first_arg, "query", None)
                top_k = getattr(first_arg, "top_k", None)
        if "tool_input" in kwargs:
            tool_input = kwargs["tool_input"]
            if isinstance(tool_input, dict):
                query = tool_input.get("query") or query
                top_k = tool_input.get("top_k") if top_k is None else top_k
            else:
                query = getattr(tool_input, "query", query)
                top_k = getattr(tool_input, "top_k", top_k)
        query = kwargs.get("query", query)
        top_k = kwargs.get("top_k", top_k)
        if query is None:
            raise TypeError("Missing required argument 'query'")
        return self._run(query=query, top_k=top_k)

    # pylint: disable=unused-argument
    def _run(self, query: str, top_k: Optional[int] = None) -> str:  # type: ignore[override]
        retriever = self._ensure_retriever()
        self._configure_top_k(retriever, top_k)
        documents = retriever.get_relevant_documents(query)
        formatted = self._format_documents(documents)
        if not formatted:
            return "No relevant information found in Azure AI Search."
        return "\n\n".join(doc.format() for doc in formatted)

    async def _arun(self, query: str, top_k: Optional[int] = None) -> str:  # type: ignore[override]
        raise NotImplementedError("AzureAISearchTool does not support async execution")

    # ------------------------------------------------------------------
    def _ensure_retriever(self) -> Any:
        if self._retriever is None:
            missing = [
                name
                for name, value in (
                    ("AZURE_SEARCH_ENDPOINT", self.endpoint),
                    ("AZURE_SEARCH_API_KEY", self.api_key),
                    ("AZURE_SEARCH_INDEX_NAME", self.index_name),
                )
                if not value
            ]
            missing_env = ", ".join(missing)
            raise RuntimeError(
                "Azure AI Search retriever is not configured."
                + (f" Missing settings: {missing_env}" if missing_env else "")
            )
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


@tool("azure_ai_search", description=TOOL_DESCRIPTION)
def azure_ai_search(query: str) -> str:
    """Tool entry-point that instantiates :class:`AzureAISearchTool`."""

    return AzureAISearchTool().run(query=query)

