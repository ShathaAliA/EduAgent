import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage

from agent import agent
from instructor_agent import run_designer_dialogue, generate_syllabus, instructor_reply
from orchestrator import classify_intent
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


RESTART_ACTION = cl.Action(
    name="restart",
    payload={},
    label="🔄 Start Over",
)

RESET_KEYWORDS = ("menu", "back", "رجوع", "القائمة", "restart", "start over")


async def reset_session():
    """يصفّر حالة الجلسة بالكامل ويرسل رسالة الترحيب الموحّدة (بدون أزرار اختيار)."""
    cl.user_session.set("mode", None)
    cl.user_session.set("stage", None)
    cl.user_session.set("history", [])
    cl.user_session.set("syllabus", None)

    await cl.Message(
        content="""
# 🎓 AI Study Assistant
Hi! 👋 I can help you with two things:

- 📚 **Plan an assignment** — tell me its name, deadline, difficulty, and estimated time
- 🎓 **Learn a new topic** — tell me what you'd like to learn

Just tell me what you need — I'll figure out which one fits automatically! 🤖
""",
        actions=[RESTART_ACTION],
    ).send()


@cl.on_chat_start
async def start():
    await reset_session()


@cl.action_callback("restart")
async def on_restart(action: cl.Action):
    await reset_session()


@cl.on_message
async def main(message: cl.Message):
    # يسمح للمستخدم يعيد البدء بالكتابة أيضاً، مو بس بالزر
    if message.content.strip().lower() in RESET_KEYWORDS:
        await reset_session()
        return

    mode = cl.user_session.get("mode")

    # 🧭 Router Agent: أول رسالة بدون وكيل محدد بعد → صنّف النية ووجّه تلقائياً
    if mode is None:
        thinking = cl.Message(content="🧭 Figuring out the best assistant for you...")
        await thinking.send()

        intent = await classify_intent(message.content)

        if intent == "unclear":
            await cl.Message(
                content=(
                    "🤔 I'm not sure if you want assignment planning or to "
                    "learn a topic. Could you clarify? For example:\n"
                    "- *\"I want to learn the basics of Python\"*\n"
                    "- *\"Assignment: Report, Deadline: 2026-09-15, "
                    "Difficulty: Medium, Estimated time: 6 hours\"*"
                ),
                actions=[RESTART_ACTION],
            ).send()
            return

        cl.user_session.set("mode", intent)
        cl.user_session.set("stage", "awaiting_topic" if intent == "instructor" else None)

        routed_label = "📚 Assignment Planner" if intent == "planner" else "🎓 AI Instructor"
        await cl.Message(content=f"Routing you to **{routed_label}** ✅").send()

        mode = intent

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
        await cl.Message(content=BLOCKED_INPUT_MESSAGE, actions=[RESTART_ACTION]).send()
        return

    response = await agent.ainvoke(
        {"messages": [{"role": "user", "content": message.content}]}
    )
    raw = response["messages"][-1].content
    final_message = format_content(raw)

    # 🛡️ فحص المخرج قبل ما يوصل للطالب
    output_check = await check_output(final_message, PLANNER_SCOPE)
    if not output_check.allowed:
        await cl.Message(content=BLOCKED_OUTPUT_MESSAGE, actions=[RESTART_ACTION]).send()
        return

    await cl.Message(content=final_message, actions=[RESTART_ACTION]).send()


# ---------------------------------------------------------------------------
# مسار 2: AI Instructor
# ---------------------------------------------------------------------------
async def handle_instructor(message: cl.Message):
    # 🛡️ فحص المدخل قبل ما يوصل للـ agent
    input_check = await check_input(message.content, INSTRUCTOR_SCOPE)
    if not input_check.allowed:
        await cl.Message(content=BLOCKED_INPUT_MESSAGE, actions=[RESTART_ACTION]).send()
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
            await cl.Message(content=BLOCKED_OUTPUT_MESSAGE, actions=[RESTART_ACTION]).send()
            return

        cl.user_session.set("syllabus", syllabus)
        cl.user_session.set("stage", "teaching")

        await cl.Message(
            content=(
                f"## 🗂️ Your Learning Syllabus\n\n{syllabus}\n\n---\n"
                "Ready to start? Type \"start\" or ask me anything about the first topic 🚀"
            ),
            actions=[RESTART_ACTION],
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
        await cl.Message(content=BLOCKED_OUTPUT_MESSAGE, actions=[RESTART_ACTION]).send()
        return

    history.append(HumanMessage(content=message.content))
    history.append(AIMessage(content=reply))
    cl.user_session.set("history", history)

    await cl.Message(content=reply, actions=[RESTART_ACTION]).send()