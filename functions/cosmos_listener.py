import logging
import os
import azure.functions as func
from function_app import app


# Listens to inserts/updates in a Cosmos DB container.
# Ensure a 'leases' container exists (or set a different lease container name).
@app.cosmos_db_trigger(
    arg_name="documents",
    connection="CosmosDbConnection",
    database_name=os.getenv("CosmosDatabase", "db"),
    container_name=os.getenv("CosmosContainer", "items"),
    lease_container_name="leases",
)
def cosmos_listener(documents: func.DocumentList) -> None:
    if documents:
        logging.info("Cosmos DB change feed batch size: %d", len(documents))
        for doc in documents:
            logging.info("Doc id=%s", doc.get("id"))
