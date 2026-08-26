from datetime import datetime
from langchain_core.tools import tool


@tool
def days_until_deadline(deadline: str) -> str:
    """
    Calculate the number of days remaining until an assignment deadline.

    The deadline must be provided in YYYY-MM-DD format.
    """

    try:
        deadline_date = datetime.strptime(deadline, "%Y-%m-%d").date()
        today = datetime.now().date()

        days = (deadline_date - today).days

        if days < 0:
            return "The deadline has already passed."

        if days == 0:
            return "The deadline is today."

        return f"{days} days remaining until the deadline."

    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD."