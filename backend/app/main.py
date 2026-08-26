import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage

from agent import agent
from instructor_agent import run_designer_dialogue, generate_syllabus, instructor_reply
from guardrails import (
    check_input,
    check_output,
    PLANNER_SCOPE,
    INSTRUCTOR_SCOPE,
    BLOCKED_INPUT_MESSAGE,
    BLOCKED_OUTPUT_MESSAGE,
)


def format_content(raw) -> str:
    """يحوّل رد الموديل (اللي أحياناً يرجع كـ list of blocks) إلى نص Markdown نظيف."""
    if isinstance(raw, list):
        text = "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in raw
        )
    else:
        text = str(raw)
    return text.replace("\\n", "\n").strip()


MENU_ACTION = cl.Action(
    name="back_to_menu",
    payload={},
    label="🔙 Back to Menu",
)


async def show_menu():
    """يعرض شاشة اختيار الوكيل ويصفّر حالة الجلسة."""
    res = await cl.AskActionMessage(
        content="Hi 👋 Which assistant would you like to use?",
        actions=[
            cl.Action(
                name="planner",
                payload={"value": "planner"},
                label="📚 Assignment Planner",
            ),
            cl.Action(
                name="instructor",
                payload={"value": "instructor"},
                label="🎓 AI Instructor",
            ),
        ],
    ).send()

    mode = "planner"
    if res and isinstance(res, dict):
        mode = res.get("payload", {}).get("value", "planner")

    cl.user_session.set("mode", mode)
    cl.user_session.set("stage", "awaiting_topic" if mode == "instructor" else None)
    cl.user_session.set("history", [])
    cl.user_session.set("syllabus", None)

    if mode == "planner":
        await cl.Message(
            content="""
# 📚 Assignment Planner Agent
Hi! 👋
I can help you create a realistic plan for your assignments.
Please provide:
- **Assignment name**
- **Deadline**
- **Difficulty** (Easy / Medium / Hard)
- **Estimated time**
### Example
Assignment: Cybersecurity Report  
Deadline: 2026-08-30  
Difficulty: Hard  
Estimated time: 6 hours
""",
            actions=[MENU_ACTION],
        ).send()
    else:
        await cl.Message(
            content="""
# 🎓 AI Instructor
Hi! 👋 What would you like to learn today?
Tell me your topic and your goal, e.g.
*"I want to learn the basics of Python for data analysis"*
""",
            actions=[MENU_ACTION],
        ).send()


@cl.on_chat_start
async def start():
    await show_menu()


@cl.action_callback("back_to_menu")
async def on_back_to_menu(action: cl.Action):
    await show_menu()


@cl.on_message
async def main(message: cl.Message):
    # يسمح للمستخدم يرجع للقائمة بالكتابة أيضاً، مو بس بالزر
    if message.content.strip().lower() in ("menu", "back", "رجوع", "القائمة"):
        await show_menu()
        return

    mode = cl.user_session.get("mode")

    if mode == "planner":
        await handle_planner(message)
    else:
        await handle_instructor(message)


# ---------------------------------------------------------------------------
# مسار 1: Assignment Planner
# ---------------------------------------------------------------------------
async def handle_planner(message: cl.Message):
    # 🛡️ فحص المدخل قبل ما يوصل للـ agent
    input_check = await check_input(message.content, PLANNER_SCOPE)
    if not input_check.allowed:
        await cl.Message(content=BLOCKED_INPUT_MESSAGE, actions=[MENU_ACTION]).send()
        return

    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": message.content}]}
    )
    raw = response["messages"][-1].content
    final_message = format_content(raw)

    # 🛡️ فحص المخرج قبل ما يوصل للطالب
    output_check = await check_output(final_message, PLANNER_SCOPE)
    if not output_check.allowed:
        await cl.Message(content=BLOCKED_OUTPUT_MESSAGE, actions=[MENU_ACTION]).send()
        return

    await cl.Message(content=final_message, actions=[MENU_ACTION]).send()


# ---------------------------------------------------------------------------
# مسار 2: AI Instructor
# ---------------------------------------------------------------------------
async def handle_instructor(message: cl.Message):
    # 🛡️ فحص المدخل قبل ما يوصل للـ agent (لكل الرسائل، أول رسالة أو أثناء التدريس)
    input_check = await check_input(message.content, INSTRUCTOR_SCOPE)
    if not input_check.allowed:
        await cl.Message(content=BLOCKED_INPUT_MESSAGE, actions=[MENU_ACTION]).send()
        return

    stage = cl.user_session.get("stage")

    if stage == "awaiting_topic":
        topic = message.content

        thinking = cl.Message(content="🤔 Designing a suitable syllabus for you...")
        await thinking.send()

        dialogue = await run_designer_dialogue(topic)
        syllabus = await generate_syllabus(topic, dialogue)

        # 🛡️ فحص المخرج (المنهج) قبل عرضه
        output_check = await check_output(syllabus, INSTRUCTOR_SCOPE)
        if not output_check.allowed:
            await cl.Message(content=BLOCKED_OUTPUT_MESSAGE, actions=[MENU_ACTION]).send()
            return

        cl.user_session.set("syllabus", syllabus)
        cl.user_session.set("stage", "teaching")

        await cl.Message(
            content=(
                f"## 🗂️ Your Learning Syllabus\n\n{syllabus}\n\n---\n"
                "Ready to start? Type \"start\" or ask me anything about the first topic 🚀"
            ),
            actions=[MENU_ACTION],
        ).send()
        return

    # stage == "teaching"
    syllabus = cl.user_session.get("syllabus")
    history = cl.user_session.get("history")

    reply_raw = await instructor_reply(history, syllabus, message.content)
    reply = format_content(reply_raw)

    # 🛡️ فحص المخرج قبل عرضه
    output_check = await check_output(reply, INSTRUCTOR_SCOPE)
    if not output_check.allowed:
        await cl.Message(content=BLOCKED_OUTPUT_MESSAGE, actions=[MENU_ACTION]).send()
        return

    history.append(HumanMessage(content=message.content))
    history.append(AIMessage(content=reply))
    cl.user_session.set("history", history)

    await cl.Message(content=reply, actions=[MENU_ACTION]).send()