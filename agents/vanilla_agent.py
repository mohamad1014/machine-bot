from __future__ import annotations

"""Base agent implementation shared by all agents."""

import json
import os
from pathlib import Path
from typing import Any, Iterable

try:  # pragma: no cover - optional dependency
    from langchain_openai import AzureChatOpenAI
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.memory import ConversationBufferMemory
except Exception:  # pragma: no cover
    AzureChatOpenAI = None  # type: ignore[assignment]
    AgentExecutor = create_tool_calling_agent = ChatPromptTemplate = MessagesPlaceholder = ConversationBufferMemory = None  # type: ignore


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
        self.tools = list(tools or [])

        deployment_name = self.config.get("model") or os.environ.get(
            "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"
        )
        llm = AzureChatOpenAI(deployment_name=deployment_name)

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
