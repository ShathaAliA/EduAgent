import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from tools import days_until_deadline


load_dotenv()


llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.2,
)


SYSTEM_PROMPT = """
You are an Assignment Planner Agent.

Your job is to help students plan their assignments.

You should consider:
- Assignment name
- Deadline
- Difficulty
- Estimated completion time

When a deadline is provided, use the days_until_deadline tool
to calculate the remaining time.

Then create a realistic and organized study plan.

The plan should:
1. Break the assignment into smaller tasks.
2. Distribute the estimated time across the available days.
3. Prioritize difficult assignments.
4. Leave some time for review before the deadline.
5. Clearly show the plan in a simple format.

If important information is missing, ask the user for it.

Do not invent a deadline or estimated time.
"""


agent = create_react_agent(
    model=llm,
    tools=[days_until_deadline],
    prompt=SYSTEM_PROMPT,
)