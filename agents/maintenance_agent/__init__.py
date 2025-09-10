from __future__ import annotations

"""Maintenance agent derived from :class:`VanillaAgent`."""

from pathlib import Path

from ..vanilla_agent import VanillaAgent


class MaintenanceAgent(VanillaAgent):
    """Agent responsible for maintenance related queries."""

    def __init__(self) -> None:
        config_dir = Path(__file__).parent
        super().__init__(
            config_path=config_dir / "config.json",
            instructions_path=config_dir / "instructions.md",
            tools=[],
        )
