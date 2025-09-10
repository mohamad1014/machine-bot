from __future__ import annotations

"""Dispatcher agent derived from :class:`VanillaAgent`.

This agent decides whether to answer the user directly or route the
question to a specialised sub-agent such as the manuals or maintenance
agent. Sub-agents are exposed to the dispatcher as tools so that the LLM
can decide when to call them.
"""

from pathlib import Path

from langchain.tools import Tool

from ..vanilla_agent import VanillaAgent
from ..manual_agent import ManualAgent
from ..maintenance_agent import MaintenanceAgent


def _agent_tool(agent: VanillaAgent) -> Tool:
    """Wrap ``agent.invoke`` in a langchain :class:`Tool` returning plain text."""

    def _run(input_text: str) -> str:
        result = agent.invoke(input_text)
        return result.get("output") if isinstance(result, dict) else str(result)

    return Tool(name=agent.config["id"], description=agent.config["description"], func=_run)


class DispatcherAgent(VanillaAgent):
    """Agent that routes requests to other agents."""

    def __init__(self) -> None:
        config_dir = Path(__file__).parent
        manual = ManualAgent()
        maintenance = MaintenanceAgent()
        tools = [_agent_tool(manual), _agent_tool(maintenance)]
        self.manual_agent = manual
        self.maintenance_agent = maintenance
        super().__init__(
            config_path=config_dir / "config.json",
            instructions_path=config_dir / "instructions.md",
            tools=tools,
        )
