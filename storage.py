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
JOURNAL_DATABASE_ID = "journal"
JOURNAL_ID_CONTAINER = "journal_container"


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
def read_journal(date: str = "ignored"):
    # container = client.get_database_client(DATABASE_ID).create_container_if_not_exists(JOURNAL_ID_CONTAINER,"user")
    container = client.get_database_client(JOURNAL_DATABASE_ID).get_container_client(
        JOURNAL_ID_CONTAINER
    )
    items = container.query_items("select * FROM c", enable_cross_partition_query=True)
    first = None
    for i in items:
        first = i
        break
    ic(first)
    if first is None:
        container.create_item(
            {"id": str(uuid.uuid4()), "user": "testserver", "content": ""}
        )
    else:
        content = first["content"]
        ic(content)
        return content


@app.command()
def append_journal(content: str):
    # container = client.get_database_client(DATABASE_ID).create_container_if_not_exists(JOURNAL_ID_CONTAINER,"user")
    container = client.get_database_client(JOURNAL_DATABASE_ID).get_container_client(
        JOURNAL_ID_CONTAINER
    )
    items = container.query_items("select * FROM c", enable_cross_partition_query=True)
    first = None
    for i in items:
        first = i

    assert first
    ic(first)
    ic(content)
    journal_item = first
    journal_item["content"] += f"{datetime.now()}: {content}\n"
    container.upsert_item(journal_item)


@app.command()
def list_journal():
    # container = client.get_database_client(DATABASE_ID).create_container_if_not_exists(JOURNAL_ID_CONTAINER,"user")
    container = client.get_database_client(JOURNAL_DATABASE_ID).get_container_client(
        JOURNAL_ID_CONTAINER
    )
    items = container.query_items("select * FROM c", enable_cross_partition_query=True)
    for item in items:
        ic(item)


def clear_journal(content: str = "ignored"):
    # container = client.get_database_client(DATABASE_ID).create_container_if_not_exists(JOURNAL_ID_CONTAINER,"user")
    container = client.get_database_client(JOURNAL_DATABASE_ID).get_container_client(
        JOURNAL_ID_CONTAINER
    )
    items = container.query_items("select * FROM c", enable_cross_partition_query=True)
    first = None
    for i in items:
        first = i

    assert first
    ic(first)

    journal_item = first
    journal_item["content"] = ""
    container.upsert_item(journal_item)


if __name__ == "__main__":
    app_wrap_loguru()
