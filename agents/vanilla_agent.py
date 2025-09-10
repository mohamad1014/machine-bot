from __future__ import annotations

"""Base agent implementation shared by all agents."""

import json
from importlib import import_module
import pkgutil
from pathlib import Path
from typing import Any, Iterable

try:  # pragma: no cover - optional dependency
    from langgraph_supervisor import create_supervisor
    from langchain_openai import AzureChatOpenAI
    from langchain.tools import Tool
except Exception:  # pragma: no cover
    create_supervisor = None  # type: ignore[assignment]
    AzureChatOpenAI = None  # type: ignore[assignment]
    Tool = None  # type: ignore


class VanillaAgent:
    """Generic agent wiring LLMs with optional tools.

    Subclasses should provide ``config_path`` and ``instructions_path`` and
    construct any required tool instances.
    """

    REGISTRY: dict[str, "VanillaAgent"] = {}

    def __init__(
        self,
        *,
        config_path: str | Path,
        instructions_path: str | Path,
        tools: Iterable[Any] | None = None,
    ) -> None:
        if create_supervisor is None or AzureChatOpenAI is None:
            raise RuntimeError(
                "langgraph-supervisor and langchain-openai must be installed"
            )

        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        system_prompt = Path(instructions_path).read_text(encoding="utf-8")

        if tools is None:
            tools = self._load_tools_from_config()
        self.tools = list(tools)

        model_name = self.config.get("model")
        if not model_name:
            raise ValueError("model must be specified in config")
        llm = AzureChatOpenAI(deployment_name=model_name)

        self._supervisor = create_supervisor(
            llm=llm, tools=self.tools, system_prompt=system_prompt, name=self.config["id"]
        )

        VanillaAgent.REGISTRY[self.config["id"]] = self

    def invoke(self, inputs: dict[str, Any] | str) -> Any:
        """Invoke the agent with given ``inputs`` and log tool usage."""
        if isinstance(inputs, dict):
            payload = inputs
        else:
            payload = {"input": inputs}

        return self._supervisor.invoke(payload)

    # ------------------------------------------------------------------
    # Tool and agent helpers
    def as_tool(self) -> Tool:
        """Expose this agent as a :class:`langchain.tools.Tool`."""

        def _run(input_text: str) -> str:
            result = self.invoke(input_text)
            return result.get("output") if isinstance(result, dict) else str(result)

        return Tool(
            name=self.config["id"],
            description=self.config.get("description", ""),
            func=_run,
        )

    @staticmethod
    def from_id(agent_id: str) -> "VanillaAgent":
        """Instantiate an agent given its snake_case identifier."""
        module = import_module(f"agents.{agent_id}")
        class_name = "".join(part.capitalize() for part in agent_id.split("_"))
        agent_cls = getattr(module, class_name)
        return agent_cls()

    # internal -----------------------------------------------------------
    def _load_tools_from_config(self) -> list[Any]:
        tool_names = self.config.get("tools", [])
        loaded: list[Any] = []
        for name in tool_names:
            cls = self._resolve_tool_class(name)
            loaded.append(cls())

        for agent_id in self.config.get("handover", []):
            loaded.append(self._agent_tool(agent_id))
        return loaded

    # ------------------------------------------------------------------
    def _agent_tool(self, agent_id: str) -> Tool:
        """Create a tool proxy for another agent identified by ``agent_id``."""

        def _run(input_text: str, *, agent_id: str = agent_id) -> str:
            agent = VanillaAgent.REGISTRY.get(agent_id)
            if agent is None:
                agent = VanillaAgent.from_id(agent_id)
            result = agent.invoke(input_text)
            return result.get("output") if isinstance(result, dict) else str(result)

        description = f"Handover to agent {agent_id}"
        return Tool(name=agent_id, description=description, func=_run)

    @staticmethod
    def _resolve_tool_class(name: str):
        import middleware

        for _, module_name, _ in pkgutil.iter_modules(middleware.__path__):
            module = import_module(f"middleware.{module_name}")
            if hasattr(module, name):
                return getattr(module, name)
        raise ValueError(f"Tool {name} not found in middleware modules")
