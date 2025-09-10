from __future__ import annotations

"""Dispatcher agent derived from :class:`VanillaAgent`.

This agent decides whether to answer the user directly or route the
question to a specialised sub-agent such as the manuals or maintenance
agent. Sub-agents are exposed to the dispatcher as tools so that the LLM
can decide when to call them.
"""

import json
from pathlib import Path

from ..vanilla_agent import VanillaAgent


class DispatcherAgent(VanillaAgent):
    """Agent that routes requests to other agents."""

    def __init__(self) -> None:
        config_dir = Path(__file__).parent
        config_path = config_dir / "config.json"
        instructions_path = config_dir / "instructions.md"
        config = json.loads(config_path.read_text(encoding="utf-8"))

        self.sub_agents: dict[str, VanillaAgent] = {}
        tools = []
        for agent_id in config.get("tools", []):
            agent = VanillaAgent.from_id(agent_id)
            self.sub_agents[agent_id] = agent
            tools.append(agent.as_tool())

        super().__init__(
            config_path=config_path,
            instructions_path=instructions_path,
            tools=tools,
        )
