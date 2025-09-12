import json
import logging

import azure.functions as func
from function_app import app

from langchain_core.messages import HumanMessage
from agents import build_graph, VanillaAgent


_graph = None


@app.route(route="conversationRun", auth_level=func.AuthLevel.FUNCTION)
def conversation_run(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint for running a dispatcher-driven conversation."""

    logging.info("HTTP conversationRun invoked")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(body="Invalid JSON when parsing request body", status_code=400)

    if not isinstance(body, dict):
        return func.HttpResponse(body="Invalid JSON when checking body type", status_code=400)

    input_data = body.get("input")
    logging.debug(f"Input data: {input_data}")
    if input_data is None:
        return func.HttpResponse(body="Invalid input when checking body content", status_code=400)

    global _graph
    if _graph is None:
        _graph = build_graph()

    messages = [*VanillaAgent.MEMORY, HumanMessage(content=input_data)]
    result = _graph.invoke({"messages": messages})
    VanillaAgent.MEMORY = result.get("messages", messages)
    output_msg = VanillaAgent.MEMORY[-1].content if VanillaAgent.MEMORY else ""

    return func.HttpResponse(
        json.dumps({"output": output_msg}),
        status_code=200,
        mimetype="application/json",
    )
