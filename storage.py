#!/usr/bin/env python3


from pydantic import BaseModel
import typer
from loguru import logger
from rich.console import Console
from icecream import ic
from datetime import datetime, timedelta
import azure.cosmos.cosmos_client as cosmos_client
from uuid import uuid4
import os
import dateutil.parser
from pathlib import Path

console = Console()
app = typer.Typer(no_args_is_help=True)


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
def all_files(date: str = None):
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

class JournalItemModel(BaseModel):
    id: str
    user: str
    content: str

@app.command()
def read_journal(_: str = "ignored"):
    """Read the current journal content."""
    # container = client.get_database_client(DATABASE_ID).create_container_if_not_exists(JOURNAL_ID_CONTAINER,"user")
    container = client.get_database_client(JOURNAL_DATABASE_ID).get_container_client(
        JOURNAL_ID_CONTAINER
    )
    items = [JournalItemModel(**item ) for item in container.read_all_items()]
    if len(items) == 0:
        print("No items yet, creating initial one")
        container.create_item(
            JournalItemModel(id = str(uuid4()), user = "test", content = "").model_dump()
        )
        return

    if len(items) != 1:
        print("more then one journal entry -- oops")
        ic(items)
        return

    content = items[0].content
    print(content)
    return content

@app.command()
def replace_journal(new_journal_path: str = "ignored"):
    """Replace the journal content with content from the specified file path.
    Creates a backup of the current content before replacing."""
    # container = client.get_database_client(DATABASE_ID).create_container_if_not_exists(JOURNAL_ID_CONTAINER,"user")
    container = client.get_database_client(JOURNAL_DATABASE_ID).get_container_client(
        JOURNAL_ID_CONTAINER
    )
    items = [JournalItemModel(**item ) for item in container.read_all_items()]
    if len(items) != 1:
        print("more then one journal entry -- oops")
        ic(items)
        return

    # Get the content of the first element.
    original_journal_content = items[0].content

    # backup the elesment
    date_string = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    Path(f"backup.journal.{date_string}.txt").write_text(original_journal_content)

    new_journal_content = Path(new_journal_path).read_text()
    if not len(new_journal_content) > 10:
        ic ("too short:", new_journal_content)
        return

    updated_journal_item = items[0].model_copy()
    updated_journal_item.content = new_journal_content
    container.upsert_item(updated_journal_item.model_dump())


@app.command()
def append_journal(content: str):
    """Append new content to the journal with current timestamp."""
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
    """List all journal entries in the database."""
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
