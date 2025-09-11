"""Agent package providing various specialised agents."""

from langgraph.graph import StateGraph, START, MessagesState

from .vanilla_agent import VanillaAgent
from .manual_agent import ManualAgent
from .maintenance_agent import MaintenanceAgent
from .dispatcher import DispatcherAgent


def build_graph(entry_id: str = "dispatcher"):
    """Build the global multi-agent graph starting from the given entry."""
    VanillaAgent.REGISTRY.clear()
    VanillaAgent.MEMORY = []
    VanillaAgent.from_id(entry_id)
    graph = StateGraph(MessagesState)
    for agent_id, agent in VanillaAgent.REGISTRY.items():
        graph.add_node(agent_id, agent.graph)
    graph.add_edge(START, entry_id)
    return graph.compile()


__all__ = [
    "VanillaAgent",
    "ManualAgent",
    "MaintenanceAgent",
    "DispatcherAgent",
    "build_graph",
]
