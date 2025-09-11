from __future__ import annotations

"""Base agent implementation built using LangGraph subgraphs."""

import json
from importlib import import_module
import pkgutil
from pathlib import Path
from typing import Any

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, InjectedState
from langgraph.types import Command
from langchain_core.tools import tool, InjectedToolCallId
from typing import Annotated


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
        VanillaAgent.REGISTRY[agent_id] = self

        self.tools: list[Any] = self._load_tools_from_config()

        for agent_name in self.config.get("handover", []):
            if agent_name not in VanillaAgent.REGISTRY:
                VanillaAgent.from_id(agent_name)
            self.tools.append(create_handoff_tool(agent_name=agent_name))

        model_name = self.config.get("model")
        if not model_name:
            raise ValueError("model must be specified in config")
        self.llm = AzureChatOpenAI(deployment_name=model_name)

        self.graph = self._build_graph()

    # building ------------------------------------------------------------
    def _build_graph(self):
        def call_model(state: MessagesState):
            response = self.llm.invoke(state["messages"])
            return {"messages": state["messages"] + [response]}

        graph = StateGraph(MessagesState)
        graph.add_node("llm", call_model)
        if self.tools:
            graph.add_node("tools", ToolNode(self.tools))
            graph.add_edge(START, "llm")
            graph.add_edge("llm", "tools")
            graph.add_edge("tools", "llm")
        else:
            graph.add_edge(START, "llm")
        graph.add_edge("llm", END)
        return graph.compile()

    # invocation ---------------------------------------------------------
    def invoke(self, inputs: dict[str, Any] | str) -> Any:
        if isinstance(inputs, dict):
            input_text = inputs.get("input", "")
        else:
            input_text = inputs
        messages = [*VanillaAgent.MEMORY, HumanMessage(content=input_text)]
        result = self.graph.invoke({"messages": messages})
        VanillaAgent.MEMORY = result.get("messages", messages)
        return result

    # helpers ------------------------------------------------------------
    @staticmethod
    def from_id(agent_id: str) -> "VanillaAgent":
        module = import_module(f"agents.{agent_id}")
        class_name = "".join(part.capitalize() for part in agent_id.split("_"))
        agent_cls = getattr(module, class_name)
        return agent_cls()

    def _load_tools_from_config(self) -> list[Any]:
        tool_names = self.config.get("tools", [])
        loaded: list[Any] = []
        for name in tool_names:
            loaded.append(self._resolve_tool(name))
        return loaded

    @staticmethod
    def _resolve_tool(name: str):
        import middleware

        for _, module_name, _ in pkgutil.iter_modules(middleware.__path__):
            module = import_module(f"middleware.{module_name}")
            if hasattr(module, name):
                return getattr(module, name)
        raise ValueError(f"Tool {name} not found in middleware modules")
