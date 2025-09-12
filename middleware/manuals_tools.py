from __future__ import annotations

"""Tools for fetching machine manuals from Azure Blob Storage."""

import os
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - exercised in environments without langchain
    from langchain.tools import BaseTool
    from langchain_community.document_loaders.azure_blob_storage_container import (
        AzureBlobStorageContainerLoader,
    )
    from langchain_community.document_loaders.azure_blob_storage_file import (
        AzureBlobStorageFileLoader,
    )
except Exception:  # pragma: no cover
    class BaseTool:  # minimal fallback to allow running tests without langchain
        """Simplified stand-in for :class:`langchain.tools.BaseTool`."""

        name: str = ""
        description: str = ""

        def run(self, *args, **kwargs):  # type: ignore[override]
            return self._run(*args, **kwargs)

        # pylint: disable=unused-argument
        def _run(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError

        async def _arun(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError

    AzureBlobStorageContainerLoader = AzureBlobStorageFileLoader = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from azure.storage.blob import BlobServiceClient
except Exception:  # pragma: no cover
    BlobServiceClient = None  # type: ignore[assignment]

try:  # pragma: no cover - pydantic may be absent in minimal envs
    from pydantic import BaseModel, Field, PrivateAttr
except Exception:  # pragma: no cover
    class BaseModel:  # minimal stub
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

    def Field(default, description=""):
        return default
    
    def PrivateAttr(default=None):
        return default

class ManualToolInput(BaseModel):
    """Input schema for :class:`ManualsTool`."""

    machine_name: str = Field(..., description="Name of the machine without extension")


class ManualsTool(BaseTool):
    """Fetch a machine manual from Azure Blob Storage or local fallback."""

    name: str = "manuals_tools"
    description: str = "Fetch a specific machine manual in markdown format."
    args_schema: type[BaseModel] = ManualToolInput
    connection_string: Optional[str] = None
    container_name: str = "manuals-md"
    fallback_path: Path = Path("manuals-md")
    _container_client: Optional[object] = PrivateAttr(default=None)

    def __init__(
        self,
        connection_string: Optional[str] = None,
        container_name: str = "manuals-md",
        fallback_path: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.connection_string = connection_string or os.environ.get(
            "MANUALS_MD_CONNECTION_STRING",
        )
        self.container_name = container_name
        self.fallback_path = Path(
            fallback_path
            if fallback_path is not None
            else os.environ.get("MANUALS_MD_PATH", "manuals-md"),
        )
        if self.connection_string and BlobServiceClient is not None:
            try:
                service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
                self._container_client = service_client.get_container_client(
                    self.container_name
                )
            except Exception:
                self._container_client = None

    def run(self, *args, **kwargs):
        """Flexible run wrapper to support different call signatures."""
        machine_name = None
        if "machine_name" in kwargs:
            machine_name = kwargs.get("machine_name")
        elif "tool_input" in kwargs:
            ti = kwargs.get("tool_input")
            if isinstance(ti, dict):
                machine_name = ti.get("machine_name")
            else:
                machine_name = getattr(ti, "machine_name", None)
        elif len(args) == 1:
            arg = args[0]
            if isinstance(arg, str):
                machine_name = arg
            elif isinstance(arg, dict):
                machine_name = arg.get("machine_name")
            else:
                machine_name = getattr(arg, "machine_name", None)
        if not machine_name:
            raise TypeError("Missing required argument 'machine_name'")
        return self._run(machine_name=machine_name)

    # pylint: disable=unused-argument
    def _run(self, machine_name: str) -> str:  # type: ignore[override]
        blob_name = machine_name if machine_name.endswith(".md") else f"{machine_name}.md"
        
        # Try Azure Blob Storage directly (without langchain loaders to avoid unstructured dependency)
        if self.connection_string and BlobServiceClient is not None:
            try:
                service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
                container_client = service_client.get_container_client(
                    self.container_name
                )
                blob_client = container_client.get_blob_client(blob_name)
                if blob_client.exists():
                    blob_data = blob_client.download_blob()
                    return blob_data.readall().decode("utf-8")
            except Exception:
                pass
        
        # Fallback to local file
        manual_file = self.fallback_path / blob_name
        if manual_file.exists():
            return manual_file.read_text(encoding="utf-8")
        return f"Machine file '{manual_file}' not found"

    async def _arun(self, machine_name: str) -> str:  # type: ignore[override]
        raise NotImplementedError("ManualsTool does not support async")


class FetchManualsTool(BaseTool):
    """List manuals available in the container."""

    name: str = "fetch_manuals"
    description: str = "List the names of manuals stored in the container."
    connection_string: Optional[str] = None
    container_name: str = "manuals-md"
    fallback_path: Path = Path("manuals-md")

    def __init__(
        self,
        connection_string: Optional[str] = None,
        container_name: str = "manuals-md",
        fallback_path: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.connection_string = connection_string or os.environ.get(
            "MANUALS_MD_CONNECTION_STRING",
        )
        self.container_name = container_name
        self.fallback_path = Path(
            fallback_path
            if fallback_path is not None
            else os.environ.get("MANUALS_MD_PATH", "manuals-md"),
        )

    def run(self, *args, **kwargs):
        """Flexible run wrapper for FetchManualsTool (no arguments needed)."""
        return self._run()

    # pylint: disable=unused-argument
    def _run(self) -> str:  # type: ignore[override]
        names: list[str] = []
        if self.connection_string and BlobServiceClient is not None:
            try:
                service_client = BlobServiceClient.from_connection_string(
                    self.connection_string,
                )
                container_client = service_client.get_container_client(
                    self.container_name,
                )
                for blob in container_client.list_blobs():
                    names.append(blob.name)
            except Exception:
                names = []
        if not names and self.fallback_path.exists():
            names = [p.name for p in self.fallback_path.glob("*") if p.is_file()]
        return "\n".join(names)

    async def _arun(self) -> str:  # type: ignore[override]
        raise NotImplementedError("FetchManualsTool does not support async")

from langchain_core.tools import tool


@tool("manuals_tool", description="Fetch a specific machine manual in markdown format.")
def manuals_tool(machine_name: str) -> str:
    return ManualsTool().run(machine_name=machine_name)


@tool("fetch_manuals", description="List the names of manuals stored in the container.")
def fetch_manuals() -> str:
    return FetchManualsTool().run()
