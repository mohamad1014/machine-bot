from __future__ import annotations

"""Tool for fetching machine manuals in markdown format."""

import os
from pathlib import Path
from typing import Optional, Any

try:  # pragma: no cover - exercised in environments without langchain
    from langchain.tools import BaseTool
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

    # Minimal stand-in so annotations remain valid without pydantic installed
    def PrivateAttr(default=None):  # type: ignore
        return default


class ManualToolInput(BaseModel):
    """Input schema for :class:`ManualMarkdownTool`."""

    machine_name: str = Field(..., description="Name of the machine without extension")

class ManualMarkdownTool(BaseTool):
    """Fetches a machine manual and appends it to the user's message.

    Manuals are stored as markdown blobs inside an Azure Storage container.
    The file must follow the pattern ``<machine_name>.md``. When the manual is
    retrieved successfully its contents are appended to the provided user
    message. If the blob is missing or cannot be accessed the original message
    is returned unchanged. A local path can be supplied for testing purposes as
    a fallback when no connection string is configured.
    """

    name: str = "ManualMarkdownTool"
    description: str = "A tool for handling manual markdown tasks."
    args_schema: type[BaseModel] = ManualToolInput
    connection_string: Optional[str] = None
    container_name: str = "manuals-md"
    fallback_path: Path = Path("manuals-md")
    _container_client: Any = PrivateAttr(default=None)

    def __init__(
        self,
        connection_string: Optional[str] = None,
        container_name: str = "manuals-md",
        fallback_path: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.connection_string = connection_string or os.environ.get(
            "MANUALS_MD_CONNECTION_STRING"
        )
        self.container_name = container_name
        self.fallback_path = Path(
            fallback_path
            if fallback_path is not None
            else os.environ.get("MANUALS_MD_PATH", "manuals-md")
        )
        if self.connection_string and BlobServiceClient is not None:
            try:
                service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
                self._container_client = service_client.get_container_client(
                    self.container_name
                )
            except Exception:  # pragma: no cover - handled gracefully
                self._container_client = None

    def run(self, *args, **kwargs):
        """Flexible run wrapper to support different call signatures.

        Accepts:
        - run(machine_name='...')
        - run(tool_input={'machine_name': '...'})
        - run('machine_name')
        - run(tool_input=SomePydanticModel(...))
        """
        machine_name = None
        # explicit kwarg
        if "machine_name" in kwargs:
            machine_name = kwargs.get("machine_name")
        # langchain style
        elif "tool_input" in kwargs:
            ti = kwargs.get("tool_input")
            if isinstance(ti, dict):
                machine_name = ti.get("machine_name")
            else:
                machine_name = getattr(ti, "machine_name", None)
        # single positional argument
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
        blob_name = f"{machine_name}.md"
        if self._container_client is not None:
            try:
                blob_client = self._container_client.get_blob_client(blob_name)
                # Use readall() and decode to avoid deprecated content_as_text API
                blob_data = blob_client.download_blob().readall()
                manual_text = blob_data.decode("utf-8")
                return f"{manual_text}"
            except Exception:
                # If any issue occurs during blob retrieval fall back to local path.
                pass

        manual_file = self.fallback_path / blob_name
        if manual_file.exists():
            manual_text = manual_file.read_text(encoding="utf-8")
            return f"{manual_text}"
        return "machine file not found"

    async def _arun(self, machine_name: str) -> str:  # type: ignore[override]
        raise NotImplementedError("ManualMarkdownTool does not support async")
