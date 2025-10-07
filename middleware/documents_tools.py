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
    
try:  # pragma: no cover - optional dependency
    from azure.cosmos import CosmosClient
except Exception:  # pragma: no cover - allow injection during tests
    CosmosClient = None  # type: ignore[assignment]


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


def _equal_any_filter(field: str, values: Sequence[str]) -> str | None:
    normalized = _normalize_values(values)
    if not normalized:
        return None
    comparisons = [f"{field} eq '{_escape_single_quotes(value)}'" for value in normalized]
    if len(comparisons) == 1:
        return comparisons[0]
    return "(" + " or ".join(comparisons) + ")"


def _collection_equal_any_filter(field: str, values: Sequence[str]) -> str | None:
    """Return an Azure AI Search OData filter for an OR over values in a collection.

    Produces: ``tags/any(t: t eq 'A' or t eq 'B')`` or with a single value
    ``tags/any(t: t eq 'A')``. Returns ``None`` when ``values`` are empty/blank.

    This mirrors the example required by the user instead of using ``search.in``.
    """
    normalized = _normalize_values(values)
    if not normalized:
        return None
    escaped = [_escape_single_quotes(v) for v in normalized]
    if len(escaped) == 1:
        return f"{field}/any(t: t eq '{escaped[0]}')"
    inner = " or ".join(f"t eq '{v}'" for v in escaped)
    return f"{field}/any(t: {inner})"


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
        description="Optional OR filter over the `tags` collection.These are all the possible values:1000 Rpm,22205/W33Va9A1,6007,6008 Bearing,61803-2Rsl,61803-2Rz(Sxc),61803-2Z(Ezo),61805-2Rzc3Lt1,61809-2Rz,61912,6203-2Rs1/Vc4862,6205-2Z/C3Gjn,6206,6208,6210,6211,6303-2Rsh,6307,6308-2Z,6310,Abnormal Test Curves,Acceleration/Deceleration,Airasca Test Center,Ambient Temperature Test,Angular Contact Ball Bearing,Assembly Procedure Validation,Automotive,Automotive Bearings,Automotive Component Reliability,Automotive Division,Axial Displacement,Axial Load,Axle Bearings,Bar-0420Aa,Bb1-0959-2,Bb1-2514 D,Bb1-2514 F,Bb1-2516 Cbt,Bb1-2593 Ab,Bb1-2602 E Bearings,Bb1-2678 B,Bb1-2679 C,Bb1-5508 Ca,Bb1-9001,Bb1-9004 K,Bb1-9005 Nd,Bb1-9006 Qc,Bb1-9006 Qc-Z,Bb1-9006 Ur-B,Bb1-9008Fb,Bb1-9014 Q,Bb1-9015,Bb1-9024 Fb,Bb1-9024 Fc,Bb1-9028 Bq,Bb1-9036 Cn,Bb1-9039 Ac,Bb1-9061 Aa,Bb1-9070 Ua,Bearing 6301,Bearing 6302,Bearing Assembly,Bearing Components,Bearing Efficiency,Bearing Endurance,Bearing Failure,Bearing Leakage,Bearing Load Calculation,Bearing Manufacturing,Bearing Material,Bearing Performance,Bearing Testing,Bearings,Bench Testing,Benchmarking,Benchmarking Report,Bending Moment,Bt1 0803A,Bt1 0883 (31314),C/P=1.5,Cajamar Brazil,Capacitance,Carbonitriding,Caulking Procedure,Ceramic Ball Supplier,China Factories,Clutch Bearing,Competitor Analysis,Competitor Bearing,Component Labeling,Component Qualification,Component Specification,Component Validation,Conductive Grease Bearing,Confidential Report,Confidentiality,Content Protection,Data Acquisition,Data Acquisition Interface,Deep Groove Ball Bearings,Design Validation,Design Validation Documentation,Design Validation Summary,Design Verification,Design Verification Plan,Deviation,Dgbb Grease Retention,Dgbb Test Rig,Dial Gauge,Dimensions,Durability,Dv Test,Dvp Item 20.1,E-Motor,E-Motor Component Testing,Electric Motors,Electric Vehicle (Ev),Electric Vehicles,Electrical Corrosion,Electrical Corrosion Prevention,Electrical Engineering,Electrical Insulation Testing,Electrical Properties,Endurance Test Summary,Endurance Testing,Engineering,Environmental Stress,Eol Test,Ev,Experimental Investigation Report,Explorer Bearing Replacement,Failure Analysis,Faw 435,Final Report,Flinger Assembly,Forged Ring Supplier,Founder Motor,Friction Analysis,Friction Torque,Gbc X-9088,Gbi Investigation Report,Gearbox Bearing,Geely,Gk Bra90S,Global Testing China,Gm Gem Platform,Gmw16311,Grease Comparison,Grease Filling,Grease Leakage,Grease Lubrication,Grease Performance,Grease Performance Testing,Gunai,Halo Recurrence Test,Heat Treatment,Heavy Load Performance Evaluation,Heavy Load Test,High Speed,High Speed Endurance,High Speed Test,High Speed Testing,High Temperature,High-Frequency Voltage-Tolerant Test,Hub Bearing Unit,Huixiang,Humidity Testing,Hybrid Dgbb,Icos-D1B05 Tn9,Ie4/Ie5 Motors,Impedance,Industrial Automation,Industrial Equipment,Industrial Manufacturing,Industrial Motor,Inner Ring Out-Of-Tolerance,Inovance,Input Shaft,Inquiry Management,Insulation Resistance,Integrated Cost Reduction,Internal Evaluation,Internal Report,Iso/Iec 17025:2005,Iso/Iec 17025:2017,Jiefang 435U Axle,Jinan Plant,L10 Nominal Life,Leakage Current,Lean Oil State,Load Cell,Low Temperature Test,Low Torque,Low Torque Bearings,Low-Temperature Testing,Lubrication,Lubrication Performance Verification,Machine Condition Monitoring,Material Change,Material Evaluation,Measurement Bench,Measurement Report,Measurement Results,Mechanical Engineering,Mt47,Nio,Nio 4.2/4.8,Nvh,O-Ring Creeping,Oil Flow Rate,Operating Manual,Operational Performance,Orhmis Rig,Over Speed,Over-Molding Design,Pca Test Rig,Peek Ring,Performance Evaluation,Performance Optimization,Performance Validation,Poor Oil Test,Precision Engineering,Product Benchmarking,Product Development,Product Engineering,Product Validation,Product Validation Report,Product Validation Test Report,Product Verification Report,Pts (Powertrain Systems),Quality Assurance,Quality Control,Radial Clearance C3,Residual Grease,Risk Assessment,Roller Wear,Rotating Bench Test,Rotating Machinery,Rotational Speed,Run-In Procedure,Rzr,Rzr Seals,Sagw Project,Sample Identification,Seal Behavior,Seal Change,Seal Evaluation,Seal Face Angle,Seal Integrity,Seal Measurement,Seal Type,Seal Wear,Sealing,Self-Heating,Series Production,Shanghai,Shell Turbo T68,Sinoma,Sketch 6893 B,Skf,Skf 6207/C3Vc4521,Skf Bb1-0230 Bd,Skf Bb1-3470 A,Skf S7005 Ce/Hcp4A,Skf3,Skf4,Snr 6206-F785/C3,Spalling,Special Lubrication,Specification,Specification Compliance Report,Standard 6207,Starting Torque,Statistical Summary,Steel Cage,Super High Speed Test,Supplier Change Evaluation,Sxc Factory,Technical Drawing,Technical Report,Temperature Erosion,Temperature Measurement,Temperature Rise Test,Temperature Rise Testing,Temperature Stability,Temperature Testing,Temperature Versus Speed,Test Acceptance Criteria,Test Conditions,Test Report,Test Request,Test Results,Test Rig,Test Specimen,Testing Apparatus,Testing Services,Textile,Textile Application,Thermal Cycling,Thermal Effect,Time Series Plot,Tn,Trb Stiffness,Trb Test Rig,Tsingshan,Uaes,Vibracoustic,Vibration,Visual Analysis,Vl-Gxv Grease,Vt113,Wanding,Xpeng Motors,Yutong,Zeekr E-Motor,Zhongyuan ",
    )
    top: int = Field(
        default=15,
        description="Maximum number of documents to return.",
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

    def run(self, *args: Any, **kwargs: Any) -> Any:  # noqa: D401 - wrapper
        tool_input, run_kwargs = self._prepare_run_call(*args, **kwargs)
        return super().run(tool_input, **run_kwargs)

    # pylint: disable=unused-argument
    def _run(self, **data: Any) -> str:  # type: ignore[override]
        doc_input = (
            data
            if isinstance(data, DoclingDocumentSearchInput)
            else DoclingDocumentSearchInput(**data)
        )

        payload = self._build_payload(doc_input)
        response = self._post(payload)
        total_count = response.get("@odata.count")
        results = [
            {
                "document_id": item.get("document_id"),
                "title": item.get("title"),
                "abstract": item.get("abstract"),
            }
            for item in response.get("value", [])
        ]
        return json.dumps(
            {
                "request": payload,
                "results": results,
                "total documents returned from the index after the query {@odata.count}": total_count,
            },
            indent=2,
            ensure_ascii=False,
        )

    def _prepare_run_call(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[str | dict[str, Any], dict[str, Any]]:
        """Normalize positional/keyword inputs for ``BaseTool.run``."""

        run_kwargs = dict(kwargs)

        # Positional tool input provided by LangGraph or direct calls.
        if args:
            if len(args) != 1:
                raise TypeError(
                    "docling_documents_search accepts at most one positional argument"
                )
            tool_input = self._normalize_run_input(args[0])
            return tool_input, run_kwargs

        # Explicit tool_input kwarg used by some LangChain helpers.
        if "tool_input" in run_kwargs:
            raw_input = run_kwargs.pop("tool_input")
            tool_input = self._normalize_run_input(raw_input)
            return tool_input, run_kwargs

        # Collect inline kwargs that map to the args schema fields.
        field_names = set(DoclingDocumentSearchInput.model_fields.keys())
        tool_specific: dict[str, Any] = {}
        for key in list(run_kwargs):
            if key in field_names:
                tool_specific[key] = run_kwargs.pop(key)

        if tool_specific:
            return tool_specific, run_kwargs

        raise TypeError(
            "docling_documents_search requires a query or DoclingDocumentSearchInput"
        )

    @staticmethod
    def _normalize_run_input(value: Any) -> str | dict[str, Any]:
        if isinstance(value, DoclingDocumentSearchInput):
            return value.model_dump(mode="json", exclude_none=True)
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            return {"query": value}
        raise TypeError(
            "Unsupported tool input for docling_documents_search"
        )

    # ------------------------------------------------------------------
    def _build_payload(self, data: DoclingDocumentSearchInput) -> dict[str, Any]:

        payload: dict[str, Any] = {
            "search": data.query,
            "top": data.top,
            "count": "true",
            "vectorQueries": [
                {
                "kind": "text",
                "text": data.query,
                "fields": "content_vector"
                }
            ],
            "queryType": "semantic",
            "semanticConfiguration": "default",
            "select": "document_id,title,abstract",
            # filter added dynamically below if tags (or other fields) provided
        }

        filters: list[str] = []
        # tags use explicit equality OR pattern per requirement
        tags_clause = _collection_equal_any_filter("tags", getattr(data, "tags", []))
        if tags_clause:
            filters.append(tags_clause)

        if filters:
            payload["filter"] = " and ".join(filters)

        return payload


class DoclingDocumentContentInput(BaseModel):
    """Input schema for :class:`DoclingDocumentContentTool`."""

    document_ids: list[str] = Field(
        ..., description="List of document identifiers to retrieve.", min_length=1
    )

class DoclingDocumentContentTool(BaseTool):
    """Retrieve docling test documents from Cosmos DB by identifier."""

    name: str = "docling_documents_content"
    description: str = (
        "Fetch docling test documents from the Cosmos DB container where `id` matches"
        " the supplied identifiers."
    )
    args_schema: type[BaseModel] = DoclingDocumentContentInput

    def __init__(
        self,
        *,
        connection_string: str | None = None,
        database_id: str | None = None,
        container_id: str | None = None,
        connection_env_var: str | None = None,
        database_env_var: str | None = None,
        container_env_var: str | None = None,
        container_client: Any | None = None,
        client_factory: Callable[[str], Any] | None = None,
    ) -> None:
        super().__init__()
        resolved_connection = connection_string or os.environ.get(
            connection_env_var or "CosmosDbConnection"
        )
        resolved_database = database_id or os.environ.get(
            database_env_var or "CosmosDatabase"
        )
        resolved_container = container_id or os.environ.get(
            container_env_var or "CosmosTestDocumentsContainer"
        )
        if container_client is None and not all(
            [resolved_connection, resolved_database, resolved_container]
        ):
            raise ValueError(
                "DoclingDocumentContentTool requires Cosmos connection string,"
                " database id, and container id."
            )
        object.__setattr__(self, "_connection_string", resolved_connection)
        object.__setattr__(self, "_database_id", resolved_database)
        object.__setattr__(self, "_container_id", resolved_container)
        object.__setattr__(self, "_container_client", container_client)
        object.__setattr__(self, "_client_factory", client_factory or _create_cosmos_client)

    def run(self, *args: Any, **kwargs: Any) -> Any:  # noqa: D401 - wrapper
        tool_input, run_kwargs = self._prepare_run_call(*args, **kwargs)
        return super().run(tool_input, **run_kwargs)

    def _run(self, **data: Any) -> str:  # type: ignore[override]
        content_input = DoclingDocumentContentInput(**data)

        doc_ids = _normalize_values(content_input.document_ids)
        if not doc_ids:
            raise ValueError("At least one document_id must be provided.")

        unique_ids = list(dict.fromkeys(doc_ids))
        container = self._ensure_container_client()
        documents = self._query_documents(container, unique_ids)
        ordered = [
            self._enrich_document(documents[identifier])
            for identifier in unique_ids
            if identifier in documents
        ]
        missing = [identifier for identifier in unique_ids if identifier not in documents]
        return json.dumps(
            {
                "documents": ordered,
                "missing_document_ids": missing,
            },
            indent=2,
            ensure_ascii=False,
        )

    def _prepare_run_call(
        self,
        *args: Any,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Normalize inbound arguments before delegating to ``BaseTool.run``."""

        run_kwargs = dict(kwargs)

        if args:
            if len(args) != 1:
                raise TypeError(
                    "docling_documents_content accepts at most one positional argument"
                )
            tool_input = self._normalize_run_input(args[0])
            return tool_input, run_kwargs

        if "tool_input" in run_kwargs:
            raw_input = run_kwargs.pop("tool_input")
            tool_input = self._normalize_run_input(raw_input)
            return tool_input, run_kwargs

        field_names = set(DoclingDocumentContentInput.model_fields.keys())
        tool_specific: dict[str, Any] = {}
        for key in list(run_kwargs):
            if key in field_names:
                tool_specific[key] = run_kwargs.pop(key)

        if tool_specific:
            return tool_specific, run_kwargs

        raise TypeError(
            "docling_documents_content requires DoclingDocumentContentInput data"
        )

    @staticmethod
    def _normalize_run_input(value: Any) -> dict[str, Any]:
        if isinstance(value, DoclingDocumentContentInput):
            return value.model_dump(mode="json", exclude_none=True)
        if isinstance(value, dict):
            return value
        raise TypeError(
            "Unsupported tool input for docling_documents_content"
        )

    def _ensure_container_client(self) -> Any:
        if self._container_client is not None:
            return self._container_client
        if CosmosClient is None:  # pragma: no cover - optional dependency path
            raise RuntimeError(
                "The 'azure-cosmos' package is required to use DoclingDocumentContentTool."
            )
        client = self._client_factory(self._connection_string)
        database = client.get_database_client(self._database_id)
        container = database.get_container_client(self._container_id)
        object.__setattr__(self, "_container_client", container)
        return container
    @staticmethod
    def _query_documents(container: Any, identifiers: list[str]) -> dict[str, dict[str, Any]]:
        if not identifiers:
            return {}
        placeholders = ", ".join(f"@id{index}" for index in range(len(identifiers)))
        query = f"SELECT * FROM c WHERE c.id IN ({placeholders})"
        parameters = [
            {"name": f"@id{index}", "value": identifier}
            for index, identifier in enumerate(identifiers)
        ]
        documents: dict[str, dict[str, Any]] = {}
        for item in container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True,
        ):
            identifier = item.get("id")
            if isinstance(identifier, str):
                documents[identifier] = item
        return documents
    @staticmethod
    def _enrich_document(document: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(document)
        enriched.setdefault("document_id", enriched.get("id"))
        return enriched
def _create_cosmos_client(connection_string: str | None) -> Any:
    if not connection_string:
        raise ValueError("Cosmos connection string must be provided.")
    if CosmosClient is None:  # pragma: no cover - optional dependency path
        raise RuntimeError(
            "The 'azure-cosmos' package is required to create Cosmos clients."
        )
    return CosmosClient.from_connection_string(connection_string)


__all__ = [
    "AzureSearchToolBase",
    "DoclingDocumentSearchInput",
    "DoclingDocumentSearchTool",
    "DoclingDocumentContentInput",
    "DoclingDocumentContentTool",
]
