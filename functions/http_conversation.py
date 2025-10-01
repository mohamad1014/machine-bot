import json
import logging
import uuid

import azure.functions as func
from function_app import app

from langchain_core.messages import AIMessage, HumanMessage
from agents import build_graph
from middleware.conversation_store import ConversationStore


_graph = None
_store: ConversationStore | None = None

def _get_store() -> ConversationStore:
    global _store
    if _store is None:
        _store = ConversationStore()
    return _store


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

    conversation_id = body.get("conversation_id")
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        return func.HttpResponse(body="conversation_id is required", status_code=400)
    conversation_id = conversation_id.strip()

    input_data = body.get("input")
    logging.debug(f"Input data: {input_data}")
    if input_data is None:
        return func.HttpResponse(body="Invalid input when checking body content", status_code=400)

    global _graph
    if _graph is None:
        _graph = build_graph()

    store = _get_store()
    history = list(store.load_messages(conversation_id))
    messages = [*history, HumanMessage(content=input_data)]
    result = _graph.invoke({"messages": messages})
    result_messages = list(result.get("messages", messages))
    store.save_messages(conversation_id, result_messages)

    output_msg: object = ""
    for message in reversed(result_messages):
        if isinstance(message, AIMessage):
            output_msg = message.content
            break

    return func.HttpResponse(
        json.dumps({"output": output_msg}),
        status_code=200,
        mimetype="application/json",
    )


@app.route(
    route="conversationReset",
    methods=["POST"],
    auth_level=func.AuthLevel.FUNCTION,
)
def conversation_reset(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint for clearing shared conversation state."""

    logging.info("HTTP conversationReset invoked")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(body="Invalid JSON when parsing request body", status_code=400)

    if not isinstance(body, dict):
        return func.HttpResponse(body="Invalid JSON when checking body type", status_code=400)

    conversation_id = body.get("conversation_id")
    if conversation_id is not None:
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            return func.HttpResponse(body="conversation_id is required", status_code=400)
        conversation_id = conversation_id.strip()

    new_conversation_id = str(uuid.uuid4())

    global _graph
    _graph = None

    return func.HttpResponse(
        json.dumps(
            {
                "status": "reset",
                "conversation_id": new_conversation_id,
                "previous_conversation_id": conversation_id,
            }
        ),
        status_code=200,
        mimetype="application/json",
    )
