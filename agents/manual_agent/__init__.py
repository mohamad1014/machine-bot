from __future__ import annotations

"""Manuals agent built on top of :class:`VanillaAgent`."""

from pathlib import Path

from ..vanilla_agent import VanillaAgent
from middleware.manuals_tools import ManualsTool, FetchManualsTool


class ManualAgent(VanillaAgent):
    """Agent wired with manuals lookup tools."""

    def __init__(
        self,
        *,
        connection_string: str | None = None,
        container_name: str = "manuals-md",
        fallback_path: str | None = None,
    ) -> None:
        config_dir = Path(__file__).parent
        manuals_tool = ManualsTool(
            connection_string=connection_string,
            container_name=container_name,
            fallback_path=fallback_path,
        )
        fetch_tool = FetchManualsTool(
            connection_string=connection_string,
            container_name=container_name,
            fallback_path=fallback_path,
        )
        super().__init__(
            config_path=config_dir / "config.json",
            instructions_path=config_dir / "instructions.md",
            tools=[manuals_tool, fetch_tool],
        )
