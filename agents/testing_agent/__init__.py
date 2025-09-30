from __future__ import annotations

"""Testing agent focused on bearing testing reports retrieval tools."""

from pathlib import Path

from ..vanilla_agent import VanillaAgent


class TestingAgent(VanillaAgent):
    """Agent wired with tools for retrieving physical testing reports."""

    def __init__(self) -> None:
        config_dir = Path(__file__).parent
        super().__init__(
            config_path=config_dir / "config.json",
            instructions_path=config_dir / "instructions.md",
        )


# Prevent pytest from mistaking the agent class for a test container.
TestingAgent.__test__ = False
