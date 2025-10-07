from __future__ import annotations

"""Shared logging utilities for Machine Bot agents."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MethodType
from typing import Any, Iterable
from uuid import uuid4

try:  # pragma: no cover - optional dependency for blob uploads
    from azure.storage.blob import BlobServiceClient
except Exception:  # pragma: no cover - allow runtime without azure-storage-blob
    BlobServiceClient = None  # type: ignore[assignment]


DEFAULT_CONTAINER_ENV_VAR = "AGENT_LOGS_CONTAINER"
DEFAULT_CONNECTION_ENV_VAR = "AzureWebJobsStorage"


@dataclass
class AgentLoggingSettings:
    """Configuration container for per-agent logging."""

    agent_id: str
    enabled: bool = True
    level: int = logging.INFO
    save_to_blob: bool = False
    blob_container_env_var: str = DEFAULT_CONTAINER_ENV_VAR
    blob_connection_env_var: str = DEFAULT_CONNECTION_ENV_VAR
    blob_path_prefix: str | None = None

    @classmethod
    def from_config(
        cls, agent_id: str, config: dict[str, Any] | None
    ) -> "AgentLoggingSettings":
        config = config or {}
        enabled = bool(config.get("enabled", True))
        level = config.get("level", logging.INFO)
        level_value: int
        if isinstance(level, str):
            level_value = getattr(logging, level.upper(), logging.INFO)
        else:
            try:
                level_value = int(level)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                level_value = logging.INFO
        return cls(
            agent_id=agent_id,
            enabled=enabled,
            level=level_value,
            save_to_blob=bool(config.get("save_to_blob", False)),
            blob_container_env_var=config.get(
                "blob_container_env_var", DEFAULT_CONTAINER_ENV_VAR
            ),
            blob_connection_env_var=config.get(
                "blob_connection_env_var", DEFAULT_CONNECTION_ENV_VAR
            ),
            blob_path_prefix=config.get("blob_path_prefix"),
        )


class AgentMemoryLogHandler(logging.Handler):
    """Log handler that buffers formatted log messages in memory."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []
        self.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%SZ",
            )
        )

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - thin wrapper
        message = self.format(record)
        self.records.append(message)

    def reset(self) -> None:
        self.records.clear()

    def as_text(self) -> str:
        return "\n".join(self.records)


class BlobLogUploader:
    """Uploads agent log payloads to Azure Blob Storage when configured."""

    def __init__(self, settings: AgentLoggingSettings, logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger

    def upload(self, payload: str) -> None:
        if not self.settings.save_to_blob:
            return
        if not payload.strip():
            return
        if BlobServiceClient is None:
            self.logger.warning(
                "Azure Blob Storage SDK is not available; skipping log upload for %s",
                self.settings.agent_id,
            )
            return

        connection_env = self.settings.blob_connection_env_var or DEFAULT_CONNECTION_ENV_VAR
        container_env = self.settings.blob_container_env_var or DEFAULT_CONTAINER_ENV_VAR

        connection_string = os.environ.get(connection_env)
        if not connection_string:
            self.logger.warning(
                "Connection string environment variable %s is not set; skipping log upload for %s",
                connection_env,
                self.settings.agent_id,
            )
            return

        container_name = os.environ.get(container_env)
        if not container_name:
            self.logger.warning(
                "Container environment variable %s is not set; skipping log upload for %s",
                container_env,
                self.settings.agent_id,
            )
            return

        try:
            service_client = BlobServiceClient.from_connection_string(connection_string)
            container_client = service_client.get_container_client(container_name)
            blob_name = self._build_blob_name()
            container_client.upload_blob(
                name=blob_name,
                data=payload.encode("utf-8"),
                overwrite=True,
            )
            self.logger.info(
                "Uploaded agent log to blob %s/%s", container_name, blob_name
            )
        except Exception as exc:  # pragma: no cover - network/SDK failures
            self.logger.exception(
                "Failed to upload agent log for %s: %s", self.settings.agent_id, exc
            )

    def _build_blob_name(self) -> str:
        prefix = self.settings.blob_path_prefix or f"agents/{self.settings.agent_id}"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        unique = uuid4().hex
        cleaned = prefix.strip("/")
        if not cleaned:
            return f"{timestamp}-{unique}.log"
        return f"{cleaned}/{timestamp}-{unique}.log"


def _truncate(value: Any, *, limit: int = 500) -> str:
    text = str(value)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _format_args(args: Iterable[Any], kwargs: dict[str, Any]) -> str:
    arg_parts = ["Args=" + _truncate(args)] if args else []
    kw_parts = ["Kwargs=" + _truncate(kwargs)] if kwargs else []
    return " ".join(arg_parts + kw_parts)


def instrument_tool_logging(tool: Any, logger: logging.Logger, agent_id: str) -> Any:
    """Attach logging hooks to a tool instance or callable."""

    tool_name = getattr(tool, "name", getattr(tool, "__name__", type(tool).__name__))

    if hasattr(tool, "invoke"):
        original_invoke = tool.invoke

        def invoke_with_logging(self, *args: Any, **kwargs: Any) -> Any:
            logger.info("Agent %s invoking tool %s", agent_id, tool_name)
            if args or kwargs:
                logger.debug(
                    "Tool %s input: %s", tool_name, _format_args(args, kwargs)
                )
            result = original_invoke(*args, **kwargs)
            logger.info(
                "Agent %s tool %s result: %s",
                agent_id,
                tool_name,
                _truncate(result),
            )
            return result

        tool.invoke = MethodType(invoke_with_logging, tool)

        if hasattr(tool, "ainvoke"):
            original_ainvoke = tool.ainvoke

            async def ainvoke_with_logging(self, *args: Any, **kwargs: Any) -> Any:
                logger.info("Agent %s invoking tool %s asynchronously", agent_id, tool_name)
                if args or kwargs:
                    logger.debug(
                        "Tool %s async input: %s",
                        tool_name,
                        _format_args(args, kwargs),
                    )
                result = await original_ainvoke(*args, **kwargs)
                logger.info(
                    "Agent %s tool %s async result: %s",
                    agent_id,
                    tool_name,
                    _truncate(result),
                )
                return result

            tool.ainvoke = MethodType(ainvoke_with_logging, tool)

        setattr(tool, "logger", logger)
        return tool

    if callable(tool):
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger.info("Agent %s invoking tool %s", agent_id, tool_name)
            if args or kwargs:
                logger.debug(
                    "Tool %s input: %s", tool_name, _format_args(args, kwargs)
                )
            result = tool(*args, **kwargs)
            logger.info(
                "Agent %s tool %s result: %s",
                agent_id,
                tool_name,
                _truncate(result),
            )
            return result

        for attr in ("name", "description", "args_schema", "__name__", "__doc__"):
            if hasattr(tool, attr):
                setattr(wrapper, attr, getattr(tool, attr))
        if hasattr(tool, "__dict__"):
            wrapper.__dict__.update(getattr(tool, "__dict__"))
        setattr(wrapper, "logger", logger)
        return wrapper

    return tool


__all__ = [
    "AgentLoggingSettings",
    "AgentMemoryLogHandler",
    "BlobLogUploader",
    "instrument_tool_logging",
]
