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
        return func.HttpResponse(status_code=400)

    if not isinstance(body, dict):
        return func.HttpResponse(status_code=400)

    machine_name = body.get("machine_name")
    input_data = body.get("input")

    if machine_name is None or input_data is None:
        return func.HttpResponse(status_code=400)

    global _agent
    if _agent is None:
        _agent = create_manual_agent()

    result = _agent.invoke({"input": input_data, "machine_name": machine_name})
    output = result.get("output") if isinstance(result, dict) else result

    return func.HttpResponse(
        json.dumps({"output": output}),
        status_code=200,
        mimetype="application/json",
    )
