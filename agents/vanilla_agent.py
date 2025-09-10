from __future__ import annotations

"""Base agent implementation shared by all agents."""

import json
from importlib import import_module
import pkgutil
from pathlib import Path
from typing import Any, Iterable

try:  # pragma: no cover - optional dependency
    from langchain_openai import AzureChatOpenAI
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.memory import ConversationBufferMemory
    from langchain.tools import Tool
except Exception:  # pragma: no cover
    AzureChatOpenAI = None  # type: ignore[assignment]
    AgentExecutor = create_tool_calling_agent = ChatPromptTemplate = MessagesPlaceholder = ConversationBufferMemory = Tool = None  # type: ignore


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
        memory: ConversationBufferMemory | None = None,
    ) -> None:
        if AzureChatOpenAI is None or AgentExecutor is None:
            raise RuntimeError("langchain and langchain-openai must be installed")

        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        system_prompt = Path(instructions_path).read_text(encoding="utf-8")

        # shared memory across agents
        self.memory = memory or ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )

        if tools is None:
            tools = self._load_tools_from_config()
        self.tools = list(tools)

        model_name = self.config.get("model")
        if not model_name:
            raise ValueError("model must be specified in config")
        llm = AzureChatOpenAI(deployment_name=model_name)

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder("chat_history"),
                ("user", "{input}"),
                MessagesPlaceholder("agent_scratchpad"),
            ]
        )

        agent = create_tool_calling_agent(llm, self.tools, prompt)
        self._executor = AgentExecutor(
            agent=agent, tools=self.tools, verbose=True, memory=self.memory
        )

        VanillaAgent.REGISTRY[self.config["id"]] = self

    def invoke(self, inputs: dict[str, Any] | str) -> Any:
        """Invoke the agent with given ``inputs`` and log tool usage."""
        if isinstance(inputs, dict):
            payload = inputs
        else:
            payload = {"input": inputs}

        result = self._executor.invoke(
            payload, return_intermediate_steps=True
        )
        steps = result.pop("intermediate_steps", [])
        if steps:
            lines = []
            for action, observation in steps:
                lines.append(
                    f"tool={action.tool} input={action.tool_input!r} output={observation!r}"
                )
            self.memory.chat_memory.add_ai_message("\n".join(lines))
        return result

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
    def from_id(agent_id: str, *, memory: ConversationBufferMemory | None = None) -> "VanillaAgent":
        """Instantiate an agent given its snake_case identifier."""
        module = import_module(f"agents.{agent_id}")
        class_name = "".join(part.capitalize() for part in agent_id.split("_"))
        agent_cls = getattr(module, class_name)
        return agent_cls(memory=memory)

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
                agent = VanillaAgent.from_id(agent_id, memory=self.memory)
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
