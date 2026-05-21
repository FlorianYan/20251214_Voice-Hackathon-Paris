import os

import requests
from notion_client import Client

_notion = None


def _get_client():
    global _notion
    if _notion is None:
        api_key = os.environ.get("NOTION_API_KEY")
        if not api_key:
            raise ValueError("NOTION_API_KEY not found in environment variables. Please add it to your .env file.")
        _notion = Client(auth=api_key)
    return _notion


def _get_page_id():
    page_id = os.environ.get("NOTION_PAGE_ID")
    if not page_id:
        raise ValueError("NOTION_PAGE_ID not found in environment variables. Please add it to your .env file.")
    return page_id


def _get_database_id():
    db_id = os.environ.get("NOTION_DATABASE_ID")
    if not db_id:
        raise ValueError("NOTION_DATABASE_ID not found in environment variables. Please add it to your .env file.")
    return db_id


def _get_headers():
    api_key = os.environ.get("NOTION_API_KEY")
    if not api_key:
        raise ValueError("NOTION_API_KEY not found in environment variables. Please add it to your .env file.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }



def _extract_text_from_blocks(blocks):
    """Internal: Extract plain text from Notion blocks."""
    text_content = []

    for block in blocks:
        block_type = block.get("type")

        if block_type in ["paragraph", "heading_1", "heading_2", "heading_3",
                          "bulleted_list_item", "numbered_list_item", "quote",
                          "callout", "code"]:
            # Get the text content from rich text
            rich_text = block.get(block_type, {}).get("rich_text", [])
            for text_obj in rich_text:
                text_content.append(text_obj.get("plain_text", ""))

        # Handle child blocks recursively if they exist
        if block.get("has_children"):
            client = _get_client()
            children = client.blocks.children.list(block["id"])
            child_text = _extract_text_from_blocks(children.get("results", []))
            text_content.append(child_text)

    return "\n".join(text_content)


def read_page():
    """
    Read the content of the configured Notion page.

    Returns:
        str: The text content of the page

    Raises:
        Exception: If there's an error accessing the Notion API
    """
    page_id = _get_page_id()

    try:
        client = _get_client()

        # Get all blocks (content) from the page
        blocks_response = client.blocks.children.list(block_id=page_id)
        blocks = blocks_response.get("results", [])

        # Extract text from all blocks
        content = _extract_text_from_blocks(blocks)

        return content

    except Exception as e:
        raise Exception(f"Error reading Notion page: {e!s}")


def write_page(text):
    """
    Write (append) text to the configured Notion page.

    Args:
        text (str): The text to append to the page

    Returns:
        bool: True if successful

    Raises:
        Exception: If there's an error accessing the Notion API
    """
    page_id = _get_page_id()

    try:
        client = _get_client()

        # Create a new paragraph block with the text
        new_block = {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": text
                        }
                    }
                ]
            }
        }

        # Append the block to the page
        client.blocks.children.append(block_id=page_id, children=[new_block])

        return True

    except Exception as e:
        raise Exception(f"Error writing to Notion page: {e!s}")


#Task Functions
def ReadTasks(filter_date=None, sort_by_priority=False):
    """
    Read all tasks from the configured Notion database.
    
    Args:
        filter_date (str, optional): Filter tasks by due date (format: "YYYY-MM-DD")
        sort_by_priority (bool, optional): Sort tasks by priority (High to Low)
    
    Returns:
        list: List of dicts with keys: "id", "Task", "Due Date", "Priority"
        
    Raises:
        Exception: If there's an error accessing the Notion API
    """
    try:
        url = f"https://api.notion.com/v1/databases/{_get_database_id()}/query"
        headers = _get_headers()
        payload = {"page_size": 100}

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])

        # Extract tasks
        tasks = []
        for page in results:
            properties = page.get("properties", {})

            # Extract Task (title) - check both "Task" and "task"
            task_prop = properties.get("Task") or properties.get("task", {})
            task_title = task_prop.get("title", [])
            task_name = task_title[0].get("plain_text", "") if task_title else ""

            # Extract Due Date (date)
            date_prop = properties.get("Due Date") or properties.get("due date", {})
            date_data = date_prop.get("date")
            due_date = date_data.get("start") if date_data else None

            # Extract Priority (select)
            priority_prop = properties.get("Priority") or properties.get("priority", {})
            priority_data = priority_prop.get("select")
            priority = priority_data.get("name") if priority_data else None

            tasks.append({
                "id": page["id"],
                "Task": task_name,
                "Due Date": due_date,
                "Priority": priority
            })

        # Filter by date if specified
        if filter_date:
            tasks = [task for task in tasks if task["Due Date"] == filter_date]

        # Sort by priority if requested
        if sort_by_priority:
            priority_order = {"High": 0, "Medium": 1, "Low": 2, None: 3}
            tasks.sort(key=lambda x: priority_order.get(x["Priority"], 3))

        return tasks

    except Exception as e:
        raise Exception(f"Error reading tasks from database: {e!s}")

def AddTask(task, due_date=None, priority=None):
    """
    Add a task to the configured Notion database.
    
    Args:
        task (str): The task name/description
        due_date (str, optional): Due date in format "YYYY-MM-DD"
        priority (str, optional): Priority level ("High", "Medium", or "Low")
        
    Returns:
        dict: The created page object
        
    Raises:
        Exception: If there's an error accessing the Notion API
    """
    try:
        url = "https://api.notion.com/v1/pages"
        headers = _get_headers()

        # Build properties for the three columns
        properties = {
            "Task": {
                "title": [{"text": {"content": task}}]
            }
        }

        # Add Due Date if provided
        if due_date:
            properties["Due Date"] = {
                "date": {"start": due_date}
            }

        # Add Priority if provided
        if priority:
            properties["Priority"] = {
                "select": {"name": priority}
            }

        # Create the page in the database
        payload = {
            "parent": {"database_id": _get_database_id()},
            "properties": properties
        }

        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        raise Exception(f"Error adding task to database: {e!s}")



def DeleteTask(task_id):
    """
    Delete (archive) a task from the configured Notion database.
    
    Args:
        task_id (str): The ID of the task to delete
        
    Returns:
        dict: The response from the API
        
    Raises:
        Exception: If there's an error accessing the Notion API
    """
    try:
        url = f"https://api.notion.com/v1/pages/{task_id}"
        headers = _get_headers()
        payload = {"archived": True}

        response = requests.patch(url, json=payload, headers=headers)
        response.raise_for_status()

        return response.json()

    except Exception as e:
        raise Exception(f"Error deleting task from database: {e!s}")
