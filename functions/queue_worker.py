import json
import logging
import azure.functions as func
from function_app import app


# Processes messages from a Storage Queue named 'tasks'
@app.queue_trigger(arg_name="msg", queue_name="tasks", connection="AzureWebJobsStorage")
def queue_worker(msg: func.QueueMessage) -> None:
    try:
        body = msg.get_body().decode("utf-8")
        logging.info("Queue message: %s", body)
        payload = json.loads(body)
        # TODO: handle task payload
        logging.info("Processed payload keys: %s", list(payload) if isinstance(payload, dict) else type(payload))
    except Exception as e:
        logging.exception("Failed to process queue message: %s", e)
