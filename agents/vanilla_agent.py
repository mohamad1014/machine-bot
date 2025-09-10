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

    def __init__(
        self,
        *,
        config_path: str | Path,
        instructions_path: str | Path,
        tools: Iterable[Any] | None = None,
    ) -> None:
        if AzureChatOpenAI is None or AgentExecutor is None:
            raise RuntimeError("langchain and langchain-openai must be installed")

        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        system_prompt = Path(instructions_path).read_text(encoding="utf-8")
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

        memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

        agent = create_tool_calling_agent(llm, self.tools, prompt)
        self._executor = AgentExecutor(
            agent=agent, tools=self.tools, verbose=True, memory=memory
        )
        self.memory = memory

    def invoke(self, inputs: dict[str, Any] | str) -> Any:
        """Invoke the agent with given ``inputs``."""
        if isinstance(inputs, dict):
            return self._executor.invoke(inputs)
        return self._executor.invoke({"input": inputs})

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
        return loaded

    @staticmethod
    def _resolve_tool_class(name: str):
        import middleware

        for _, module_name, _ in pkgutil.iter_modules(middleware.__path__):
            module = import_module(f"middleware.{module_name}")
            if hasattr(module, name):
                return getattr(module, name)
        raise ValueError(f"Tool {name} not found in middleware modules")
