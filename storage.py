#!python3


import typer
from loguru import logger
from rich.console import Console
from icecream import ic
from datetime import datetime
import azure.cosmos.cosmos_client as cosmos_client
import uuid
import os

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
def list():
    """
    List all files in the storage directory
    """
    db = client.get_database_client(DATABASE_ID)
    container = db.get_container_client(CONTAINER_ID)
    items = container.read_all_items()
    for item in items:
        ts = datetime.fromtimestamp(item["_ts"])
        ic(ts.strftime("%B %d, %Y %I:%M:%S"), item)


@app.command()
def add():
    db = client.get_database_client(DATABASE_ID)
    container = db.get_container_client(CONTAINER_ID)
    container.create_item(
        {"id": str(uuid.uuid4()), "user": "testserver", "reason": "cuz my test works"}
    )


if __name__ == "__main__":
    app_wrap_loguru()
