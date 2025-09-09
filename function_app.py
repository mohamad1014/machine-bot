import azure.functions as func

# Global Function App for the Python v2 programming model
app = func.FunctionApp()

# Import modules that register functions on the shared `app`.
# Each module should import `app` from here and attach triggers.
from functions import http_conversation  # noqa: F401
from functions import timer_cleanup  # noqa: F401
from functions import queue_worker  # noqa: F401
from functions import cosmos_listener  # noqa: F401
