"""Agent package providing various specialised agents."""

from langgraph.graph import StateGraph, START, MessagesState, END

from .vanilla_agent import VanillaAgent
from .manual_agent import ManualAgent
from .maintenance_agent import MaintenanceAgent
from .dispatcher_agent import DispatcherAgent
from langgraph.prebuilt import tools_condition

def build_graph(entry_id: str = "dispatcher_agent"):
    """Build the global multi-agent graph connecting the agent subgraphs starting from the given entry."""
    VanillaAgent.REGISTRY.clear()
    VanillaAgent.MEMORY = []
    VanillaAgent.from_id(entry_id)
    graph = StateGraph(MessagesState)
    tool_handovers = dict()
    tool_handovers["__end__"] = "__end__"
    for agent_id, agent in VanillaAgent.REGISTRY.items():
        graph.add_node(agent_id, agent.graph)
        if agent_id != entry_id:
            graph.add_edge(agent_id, entry_id)
            tool_handovers[agent_id] = agent_id
    graph.add_edge(START, entry_id)
    graph.add_conditional_edges(
                            entry_id,
                            tools_condition,  # Routes to "tools" or "__end__"
                            tool_handovers
                        )
    # graph.add_edge(entry_id, 'manual_agent')
    # graph.add_edge(entry_id, 'maintenance_agent')
    # graph.add_edge("tools", entry_id)
    # graph.add_edge(entry_id, END)
    return graph.compile()


__all__ = [
    "VanillaAgent",
    "ManualAgent",
    "MaintenanceAgent",
    "DispatcherAgent",
    "build_graph",
]
