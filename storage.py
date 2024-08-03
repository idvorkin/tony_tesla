#!python3


import typer
from loguru import logger
from rich.console import Console
from icecream import ic
from datetime import datetime, timedelta
import azure.cosmos.cosmos_client as cosmos_client
import uuid
import os
import dateutil.parser

console = Console()
app = typer.Typer()


@logger.catch()
def app_wrap_loguru():
    app()


DB_HOST = "https://tonyserver.documents.azure.com:443/"
MASTER_KEY = os.environ["TONY_STORAGE_SERVER_API_KEY"]
DATABASE_ID = "grateful"
CONTAINER_ID = "main"


client = cosmos_client.CosmosClient(
    DB_HOST,
    {"masterKey": MASTER_KEY},
    user_agent="storage.py",
    user_agent_overwrite=True,
)


@app.command()
def list(date: str = None):
    """
    List all files in the storage directory after a given date.
    If no date is provided, it defaults to 2 days ago.
    """
    if date is None:
        query_date = datetime.now() - timedelta(days=2)
    else:
        try:
            query_date = dateutil.parser.parse(date)
        except ValueError:
            logger.error(
                "Invalid date format. Please provide the date in a valid format."
            )
            return

    query = f"SELECT * FROM c WHERE c._ts > {query_date.timestamp()}"
    db = client.get_database_client(DATABASE_ID)
    container = db.get_container_client(CONTAINER_ID)
    items = container.query_items(query, enable_cross_partition_query=True)
    for item in items:
        ts = datetime.fromtimestamp(item["_ts"])
        ic(ts.strftime("%B %d, %Y %I:%M:%S"), item)


@app.command()
def add(content: str):
    db = client.get_database_client(DATABASE_ID)
    container = db.get_container_client(CONTAINER_ID)
    container.create_item(
        {"id": str(uuid.uuid4()), "user": "testserver", "content": content}
    )


if __name__ == "__main__":
    app_wrap_loguru()
