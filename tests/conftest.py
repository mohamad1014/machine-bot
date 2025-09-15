import sys
import warnings
from pathlib import Path

from pydantic import PydanticDeprecatedSince20
import types

# Add the project root directory to sys.path so that imports work correctly
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Silence deprecation warnings from pydantic v2 accessing the
# legacy `__fields__` attribute in downstream libraries.
warnings.filterwarnings("ignore", category=PydanticDeprecatedSince20)

# Provide minimal stubs for optional third-party libraries that are
# not available in the execution environment.
if "langgraph" not in sys.modules:  # pragma: no cover - defensive setup
    graph_stub = types.SimpleNamespace(
        StateGraph=object,
        START=object(),
        END=object(),
        MessagesState=dict,
    )
    prebuilt_stub = types.SimpleNamespace(
        ToolNode=object,
        InjectedState=object,
        tools_condition=lambda *args, **kwargs: None,
    )
    types_stub = types.SimpleNamespace(Command=object)
    langgraph_stub = types.SimpleNamespace(
        graph=graph_stub, prebuilt=prebuilt_stub, types=types_stub
    )
    sys.modules["langgraph"] = langgraph_stub
    sys.modules["langgraph.graph"] = graph_stub
    sys.modules["langgraph.prebuilt"] = prebuilt_stub
    sys.modules["langgraph.types"] = types_stub

    # Patch VanillaAgent to avoid relying on the real LangGraph library
    import agents.vanilla_agent as vanilla_agent  # noqa: WPS433

    def _dummy_build(self):
        import json

        class Graph:
            def invoke(_, state):
                messages = list(state["messages"])
                response = self.llm.invoke(messages)
                messages.append(response)
                tool_calls = response.additional_kwargs.get("tool_calls", [])
                if tool_calls:
                    for call in tool_calls:
                        name = call["function"]["name"]
                        args = json.loads(call["function"]["arguments"])
                        for tool in self.tools:
                            tool_name = getattr(tool, "name", getattr(tool, "__name__", ""))
                            if tool_name == name:
                                if hasattr(tool, "invoke"):
                                    result = tool.invoke(args)
                                else:  # pragma: no cover - fallback for plain callables
                                    result = tool(**args)
                                messages.append(ToolMessage(result))
                    final = self.llm.invoke(messages)
                    messages.append(final)
                return {"messages": messages}

        class ToolMessage:  # noqa: D401 - simple container used in tests
            def __init__(self, content):
                self.content = content

        return Graph()
    vanilla_agent.VanillaAgent._build_subgraph = _dummy_build

    def _dummy_handoff_tool(*, agent_name: str, description: str | None = None):
        def handoff(state=None, tool_call_id=None):  # pragma: no cover - trivial stub
            return {}

        return handoff

    vanilla_agent.create_handoff_tool = _dummy_handoff_tool
