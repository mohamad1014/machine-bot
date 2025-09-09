import json
import logging

import azure.functions as func
from function_app import app

from agents.manual_agent import create_manual_agent


_agent = None


@app.route(route="conversationRun", auth_level=func.AuthLevel.FUNCTION)
def conversation_run(req: func.HttpRequest) -> func.HttpResponse:
    """HTTP endpoint for running a manual agent conversation."""

    logging.info("HTTP conversationRun invoked")

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(body="Invalid JSON", status_code=400)

    if not isinstance(body, dict):
        return func.HttpResponse(body="Invalid JSON", status_code=400)
    
    input_data = body.get("input")
    logging.debug(f"Input data: {input_data}")
    if input_data is None:
        return func.HttpResponse(body="Invalid input", status_code=400)

    global _agent
    if _agent is None:
        _agent = create_manual_agent()

    result = _agent.invoke({"input": input_data})
    logging.debug(f"Agent result: {result}")
    output = result.get("output") if isinstance(result, dict) else result

    return func.HttpResponse(
        json.dumps({"output": output}),
        status_code=200,
        mimetype="application/json",
    )
