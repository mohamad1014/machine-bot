from __future__ import annotations

"""Tool for fetching machine manuals in markdown format."""

import os
from pathlib import Path
from typing import Optional

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
    from pydantic import BaseModel, Field
except Exception:  # pragma: no cover
    class BaseModel:  # minimal stub
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

    def Field(default, description=""):
        return default


class ManualToolInput(BaseModel):
    """Input schema for :class:`ManualMarkdownTool`."""

    machine_name: str = Field(..., description="Name of the machine without extension")
    user_message: str = Field(..., description="Original user message to append context to")


class ManualMarkdownTool(BaseTool):
    """Fetches a machine manual and appends it to the user's message.

    Manuals are stored as markdown blobs inside an Azure Storage container.
    The file must follow the pattern ``<machine_name>.md``. When the manual is
    retrieved successfully its contents are appended to the provided user
    message. If the blob is missing or cannot be accessed the original message
    is returned unchanged. A local path can be supplied for testing purposes as
    a fallback when no connection string is configured.
    """

    name = "manual_markdown_lookup"
    description = (
        "Append the markdown manual for a machine to the provided user message."
    )
    args_schema: type[BaseModel] = ManualToolInput

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
        self._container_client = None
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

    # pylint: disable=unused-argument
    def _run(self, machine_name: str, user_message: str) -> str:  # type: ignore[override]
        blob_name = f"{machine_name}.md"
        if self._container_client is not None:
            try:
                blob_client = self._container_client.get_blob_client(blob_name)
                manual_text = blob_client.download_blob().content_as_text(
                    encoding="utf-8"
                )
                return f"{user_message}\n\n{manual_text}"
            except Exception:
                # If any issue occurs during blob retrieval fall back to local path.
                pass

        manual_file = self.fallback_path / blob_name
        if manual_file.exists():
            manual_text = manual_file.read_text(encoding="utf-8")
            return f"{user_message}\n\n{manual_text}"
        return user_message

    async def _arun(self, machine_name: str, user_message: str) -> str:  # type: ignore[override]
        raise NotImplementedError("ManualMarkdownTool does not support async")
