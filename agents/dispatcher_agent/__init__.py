from __future__ import annotations

"""Dispatcher agent built on :class:`VanillaAgent`."""

from pathlib import Path

from ..vanilla_agent import VanillaAgent


class DispatcherAgent(VanillaAgent):
    """Central agent that routes requests to specialised agents."""

    def __init__(self) -> None:
        config_dir = Path(__file__).parent
        super().__init__(
            config_path=config_dir / "config.json",
            instructions_path=config_dir / "instructions.md",
        )
