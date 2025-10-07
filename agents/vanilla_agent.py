from __future__ import annotations

"""Base agent implementation built using LangGraph subgraphs."""

import json
import logging
from importlib import import_module
import pkgutil
from pathlib import Path
from typing import Any

try:  # pragma: no cover - optional dependency during minimal installs
    from langchain_core.tools import BaseTool as LangChainBaseTool
except Exception:  # pragma: no cover - fallback for tooling-free envs
    class LangChainBaseTool:  # type: ignore[too-many-ancestors]
        """Lightweight stand-in when LangChain is unavailable."""

        def __init__(self, *args, **kwargs) -> None:  # noqa: D401
            raise RuntimeError("LangChain BaseTool is required for tool configuration")

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, InjectedState, tools_condition
from langgraph.types import Command
from langchain_core.tools import tool, InjectedToolCallId
from typing import Annotated, Sequence
from langchain_core.messages.utils import convert_to_openai_messages

from .logging_utils import (
    AgentLoggingSettings,
    AgentMemoryLogHandler,
    BlobLogUploader,
    instrument_tool_logging,
)


def create_handoff_tool(*, agent_name: str, description: str | None = None):
    """Create a tool that transfers control to another agent."""
    name = f"transfer_to_{agent_name}"
    description = description or f"Transfer to {agent_name}"

    @tool(name, description=description)
    def handoff(
        state: Annotated[MessagesState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        tool_message = {
            "role": "tool",
            "content": f"Successfully transferred to {agent_name}",
            "name": name,
            "tool_call_id": tool_call_id,
        }
        return Command(
            goto=agent_name,
            update={"messages": state["messages"] + [tool_message]},
            graph=Command.PARENT,
        )

    return handoff


class VanillaAgent:
    """Generic agent wiring LLMs with optional tools and shared memory."""

    REGISTRY: dict[str, "VanillaAgent"] = {}
    MEMORY: list[BaseMessage] = []

    def __init__(
        self,
        *,
        config_path: str | Path,
        instructions_path: str | Path,
    ) -> None:
        self.config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.instructions = Path(instructions_path).read_text(encoding="utf-8")

        agent_id = self.config["id"]
        self.agent_id = agent_id

        VanillaAgent.REGISTRY[agent_id] = self

        self.logging_settings = AgentLoggingSettings.from_config(
            agent_id, self.config.get("logging")
        )
        self.logger = logging.getLogger(f"machine_bot.agent.{agent_id}")
        self.logger.setLevel(self.logging_settings.level)
        self.logger.propagate = False
        self._log_handler: AgentMemoryLogHandler | None = None
        if self.logging_settings.enabled:
            self._log_handler = AgentMemoryLogHandler()
            self.logger.handlers = [
                handler
                for handler in self.logger.handlers
                if not isinstance(handler, AgentMemoryLogHandler)
            ]
            self.logger.addHandler(self._log_handler)
        else:
            self.logger.handlers = [
                handler
                for handler in self.logger.handlers
                if not isinstance(handler, AgentMemoryLogHandler)
            ]
            if not self.logger.handlers:
                self.logger.addHandler(logging.NullHandler())
        self._blob_uploader = BlobLogUploader(self.logging_settings, self.logger)

        self.tools: list[Any] = self._load_tools_from_config()

        for agent_name in self.config.get("handover", []):
            if agent_name not in VanillaAgent.REGISTRY:
                VanillaAgent.from_id(agent_name)
            self.tools.append(create_handoff_tool(agent_name=agent_name))

        if self._log_handler:
            self.tools = [
                instrument_tool_logging(tool, self.logger, agent_id)
                for tool in self.tools
            ]

        model_name = self.config.get("model")
        if not model_name:
            raise ValueError("model must be specified in config")
        self.llm = AzureChatOpenAI(deployment_name=model_name).bind_tools(self.tools)

        self.graph = self._build_subgraph()

    # building ------------------------------------------------------------
    def _build_subgraph(self):
        def call_model(state: MessagesState):
            if self._log_handler:
                self.logger.info(
                    "Agent %s invoking model with %d message(s)",
                    self.agent_id,
                    len(state["messages"]),
                )
            msgs = [SystemMessage(content=self.instructions)] + list(state["messages"])
            msgs = convert_to_openai_messages(msgs)
            response = self.llm.invoke(msgs)
            if self._log_handler:
                self.logger.info(
                    "Agent %s model response: %s",
                    self.agent_id,
                    self._shorten(response.content),
                )
                self._log_tool_calls(response)
            airesponse = AIMessage(
                content=response.content,
                additional_kwargs=response.additional_kwargs,
                agent=self.config["displayName"],
            )
            if self._log_handler:
                self.logger.info(
                    "Agent %s recorded AI response", self.agent_id
                )
            return {"messages": state["messages"] + [airesponse]}

        graph = StateGraph(MessagesState)
        graph.add_node("llm", call_model)
        if self.tools:
            graph.add_node("tools", ToolNode(self.tools))
            graph.add_edge(START, "llm")
            graph.add_conditional_edges(
                                        "llm",
                                        tools_condition,  # Routes to "tools" or "__end__"
                                        {"tools": "tools", "__end__": "__end__"}
                                    )
            graph.add_edge("tools", "llm")

            # graph.add_edge("llm", "tools")
            # graph.add_edge("tools", "llm")
        else:
            graph.add_edge(START, "llm")
        graph.add_edge("llm", END)
        return graph.compile()

    # invocation ---------------------------------------------------------
    def invoke(
        self,
        inputs: dict[str, Any] | str,
        *,
        history: Sequence[BaseMessage] | None = None,
    ) -> Any:
        if self._log_handler:
            self._log_handler.reset()
            self.logger.info("Starting invocation for agent %s", self.agent_id)
        if isinstance(inputs, dict) and "messages" in inputs:
            raw_messages = inputs["messages"]
            if isinstance(raw_messages, Sequence) and not isinstance(raw_messages, (str, bytes)):
                messages = list(raw_messages)
            else:
                messages = [raw_messages]
        else:
            messages = list(history or [])
            if isinstance(inputs, dict):
                if "input" in inputs and inputs["input"] is not None:
                    messages.append(HumanMessage(content=inputs["input"]))
                    if self._log_handler:
                        self._log_human_message(inputs["input"])
            else:
                messages.append(HumanMessage(content=inputs))
                if self._log_handler:
                    self._log_human_message(inputs)
        result = self.graph.invoke({"messages": messages})
        if self._log_handler:
            ai_messages = [
                message
                for message in result.get("messages", [])
                if isinstance(message, AIMessage)
            ]
            if ai_messages:
                self.logger.info(
                    "Agent %s final AI response: %s",
                    self.agent_id,
                    self._shorten(ai_messages[-1].content),
                )
            self.logger.info("Completed invocation for agent %s", self.agent_id)
            self._blob_uploader.upload(self._log_handler.as_text())
        return result

    # helpers ------------------------------------------------------------
    @staticmethod
    def from_id(agent_id: str) -> "VanillaAgent":
        module = import_module(f"agents.{agent_id}")
        class_name = "".join(part.capitalize() for part in agent_id.split("_"))
        agent_cls = getattr(module, class_name)
        return agent_cls()

    def _load_tools_from_config(self) -> list[Any]:
        tool_entries = self.config.get("tools", [])
        loaded: list[Any] = []
        for entry in tool_entries:
            if isinstance(entry, str):
                loaded.append(self._resolve_tool(entry, config=None))
            elif isinstance(entry, dict):
                name = entry.get("name")
                if not name:
                    raise ValueError("Tool configuration objects must include a 'name'.")
                config = entry.get("config") or {}
                loaded.append(self._resolve_tool(name, config=config))
            else:
                raise TypeError(
                    "Each tool entry must be either a string name or a mapping with a 'name'."
                )
        return loaded

    @staticmethod
    def _resolve_tool(name: str, *, config: dict[str, Any] | None):
        import middleware

        for _, module_name, _ in pkgutil.iter_modules(middleware.__path__):
            module = import_module(f"middleware.{module_name}")
            if hasattr(module, name):
                tool = getattr(module, name)
                return VanillaAgent._apply_tool_config(tool, config)
        raise ValueError(f"Tool {name} not found in middleware modules")

    @staticmethod
    def _apply_tool_config(tool: Any, config: dict[str, Any] | None):
        if isinstance(tool, type):
            if issubclass(tool, LangChainBaseTool):
                return tool(**(config or {}))
            if config is None:
                return tool()
            return tool(**config)
        if isinstance(tool, LangChainBaseTool):
            if not config:
                return tool
            for key, value in config.items():
                setattr(tool, key, value)
            return tool
        if config:
            configure = getattr(tool, "configure", None)
            if callable(configure):
                return configure(**config)
            raise ValueError(
                f"Tool {getattr(tool, 'name', repr(tool))} does not support configuration"
            )
        return tool

    # logging helpers --------------------------------------------------
    def _shorten(self, value: Any, limit: int = 500) -> str:
        text = str(value)
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def _log_tool_calls(self, response: BaseMessage) -> None:
        if not self._log_handler:
            return
        tool_calls = getattr(response, "additional_kwargs", {}).get("tool_calls")
        if not tool_calls:
            return
        for call in tool_calls:
            function = call.get("function", {}) if isinstance(call, dict) else {}
            name = function.get("name")
            arguments = function.get("arguments")
            self.logger.info(
                "Agent %s requested tool %s with arguments %s",
                self.agent_id,
                name,
                self._shorten(arguments),
            )

    def _log_human_message(self, content: Any) -> None:
        if not self._log_handler:
            return
        self.logger.info(
            "Agent %s received human input: %s",
            self.agent_id,
            self._shorten(content),
        )

    def get_logs(self) -> list[str]:
        if not self._log_handler:
            return []
        return list(self._log_handler.records)
