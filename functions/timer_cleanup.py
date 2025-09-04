import datetime
import logging
import azure.functions as func
from function_app import app


@app.timer_trigger(schedule="0 */5 * * * *", arg_name="mytimer")
def timer_cleanup(mytimer: func.TimerRequest) -> None:
    """Runs every 5 minutes. Add periodic maintenance here."""
    utc_now = datetime.datetime.utcnow().isoformat()
    if mytimer.past_due:
        logging.warning("Timer is past due!")
    logging.info("Timer triggered at %s", utc_now)
