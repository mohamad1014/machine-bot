from __future__ import annotations

"""Manuals agent built on top of :class:`VanillaAgent`."""

from pathlib import Path

from ..vanilla_agent import VanillaAgent


class ManualAgent(VanillaAgent):
    """Agent wired with manuals lookup tools."""

    def __init__(self) -> None:
        config_dir = Path(__file__).parent
        super().__init__(
            config_path=config_dir / "config.json",
            instructions_path=config_dir / "instructions.md",
        )
