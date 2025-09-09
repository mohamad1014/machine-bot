from __future__ import annotations

"""Agent that leverages Azure OpenAI and manual lookup tools."""

import os
from typing import Any

try:  # pragma: no cover - optional dependency
    from langchain_openai import AzureChatOpenAI
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
except Exception:  # pragma: no cover
    AzureChatOpenAI = None  # type: ignore[assignment]
    AgentExecutor = create_tool_calling_agent = ChatPromptTemplate = MessagesPlaceholder = None  # type: ignore

from middleware.manuals_tools import ManualsTool, FetchManualsTool


def create_manual_agent(
    *,
    connection_string: str | None = None,
    container_name: str = "manuals-md",
    fallback_path: str | None = None,
    deployment_name: str | None = None,
) -> "AgentExecutor":
    """Create an agent wired with manuals tools.

    Parameters
    ----------
    connection_string:
        Optional Azure Storage connection string.
    container_name:
        Name of the manuals container.
    fallback_path:
        Local path to manual files for testing.
    deployment_name:
        Azure OpenAI chat deployment to target. If omitted, the
        ``AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`` environment variable is used.

    Returns
    -------
    AgentExecutor
        Configured agent capable of calling ``manuals_tools`` and ``fetch_manuals``.
    """

    if AzureChatOpenAI is None or AgentExecutor is None:
        raise RuntimeError("langchain and langchain-openai must be installed")

    manuals_tool = ManualsTool(
        connection_string=connection_string,
        container_name=container_name,
        fallback_path=fallback_path,
    )
    fetch_tool = FetchManualsTool(
        connection_string=connection_string,
        container_name=container_name,
        fallback_path=fallback_path,
    )

    llm = AzureChatOpenAI(
        deployment_name=
            deployment_name
            or os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", "gpt-4o-mini"),
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant. Use manuals_tools to fetch machine "
                "manuals or fetch_manuals to list available manuals when relevant.",
            ),
            ("user", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, [manuals_tool, fetch_tool], prompt)
    return AgentExecutor(agent=agent, tools=[manuals_tool, fetch_tool], verbose=True)
