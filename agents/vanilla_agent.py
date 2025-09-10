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
    from langchain_core.messages import AIMessage, HumanMessage, BaseMessage
except Exception:  # pragma: no cover
    create_supervisor = None  # type: ignore[assignment]
    AzureChatOpenAI = None  # type: ignore[assignment]
    AIMessage = HumanMessage = BaseMessage = None  # type: ignore


class VanillaAgent:
    """Generic agent wiring LLMs with optional tools and shared memory.

    Subclasses provide ``config_path`` and ``instructions_path`` and rely on
    this base class to wire up their language model, tools and any delegated
    agents defined in the configuration.
    """

    REGISTRY: dict[str, "VanillaAgent"] = {}
    MEMORY: list[BaseMessage] = []

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

        # register early to allow recursive handover wiring
        VanillaAgent.REGISTRY[self.config["id"]] = self

        if tools is None:
            tools = self._load_tools_from_config()
        self.tools = list(tools)

        model_name = self.config.get("model")
        if not model_name:
            raise ValueError("model must be specified in config")
        llm = AzureChatOpenAI(deployment_name=model_name)

        self.child_agents = []
        for agent_id in self.config.get("handover", []):
            agent = VanillaAgent.REGISTRY.get(agent_id)
            if agent is None:
                agent = VanillaAgent.from_id(agent_id)
            if getattr(agent, "_supervisor", None) is not None:
                self.child_agents.append(agent)

        self._supervisor = create_supervisor(
            [child._supervisor for child in self.child_agents],
            model=llm,
            tools=self.tools,
            prompt=system_prompt,
            supervisor_name=self.config["id"],
        )

    def invoke(self, inputs: dict[str, Any] | str) -> Any:
        """Invoke the agent with shared memory state."""

        if isinstance(inputs, dict):
            input_text = inputs.get("input", "")
        else:
            input_text = inputs

        messages = [*VanillaAgent.MEMORY, HumanMessage(content=input_text)]
        result = self._supervisor.invoke({"messages": messages})
        # persist updated history
        VanillaAgent.MEMORY = result.get("messages", messages)
        return result

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
        return loaded

    @staticmethod
    def _resolve_tool_class(name: str):
        import middleware

        for _, module_name, _ in pkgutil.iter_modules(middleware.__path__):
            module = import_module(f"middleware.{module_name}")
            if hasattr(module, name):
                return getattr(module, name)
        raise ValueError(f"Tool {name} not found in middleware modules")
