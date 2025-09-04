import logging
import azure.functions as func
from function_app import app


@app.route(route="conversationRun", auth_level=func.AuthLevel.FUNCTION)
def conversation_run(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("HTTP conversationRun invoked")

    name = req.params.get("name")
    if not name:
        try:
            req_body = req.get_json()
            name = req_body.get("name") if isinstance(req_body, dict) else None
        except ValueError:
            name = None

    if name:
        return func.HttpResponse(
            f"Hello, {name}. This HTTP triggered function executed successfully.",
            status_code=200,
        )

    return func.HttpResponse(
        "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
        status_code=200,
    )
