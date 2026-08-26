import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.4,
)

# ---------------------------------------------------------------------------
# شخصيات وكيلي تصميم المنهج (Role-playing designers)
# ---------------------------------------------------------------------------

DESIGNER_A_PROMPT = """You are Dr. Amina, a curriculum design expert who
focuses on PRACTICAL, hands-on, project-based learning. You believe people
learn best by doing. When discussing how to structure a syllabus for a
learner's topic, you push for real exercises, mini-projects, and applied
examples at every stage. Keep your responses conversational and concise
(3-5 sentences). You are talking with a colleague (Dr. Omar) to jointly
design a syllabus - respond to what he said and build on it or challenge it."""

DESIGNER_B_PROMPT = """You are Dr. Omar, a curriculum design expert who
focuses on THEORETICAL FOUNDATIONS and structured progression of concepts.
You believe learners need solid fundamentals before applying them. When
discussing how to structure a syllabus for a learner's topic, you push for
a logical, well-sequenced build-up of concepts, clear definitions, and
checkpoints. Keep your responses conversational and concise (3-5 sentences).
You are talking with a colleague (Dr. Amina) to jointly design a syllabus -
respond to what she said and build on it or challenge it."""

SYLLABUS_PROMPT = """You are a syllabus generator. You will be given a
learner's topic/goal and a transcript of a discussion between two
curriculum design experts (one practical, one theoretical) who debated how
to structure a course on this topic.

Your job: produce a FINAL, clean, well-organized syllabus in Markdown that
merges the best ideas from both experts. Format:

## 🎯 Learning Goal
(one line)

## 🗺️ Modules
For each module use:
### Module N: <title>
- **Objective:** ...
- **Topics:** ...
- **Practice:** (a small hands-on task)

Keep it to 3-6 modules. Do not include any commentary outside this
structure."""

INSTRUCTOR_PROMPT_TEMPLATE = """You are an adaptive AI Instructor teaching
a student based on the following syllabus:

{syllabus}

Your teaching style:
- Adapt pace and depth to how the student responds (if they seem confused,
  slow down and simplify; if they seem confident, move faster and go
  deeper).
- Teach ONE concept/module at a time, don't dump the whole syllabus at once.
- After explaining something, check understanding with a short question or
  a tiny exercise before moving on.
- Be encouraging and clear. Use simple language and examples.
- Keep track of where the student is in the syllabus based on the
  conversation history.
- ALWAYS respond in English, regardless of what language the student
  writes in."""


def extract_text(content) -> str:
    """يستخرج النص الصافي من رد الموديل، حتى لو رجع كـ list of content blocks
    (زي شكل Gemini اللي يحتوي أحياناً على 'type'/'text'/'extras')."""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        text = "".join(parts)
    else:
        text = str(content)
    return text.replace("\\n", "\n").strip()


async def run_designer_dialogue(topic: str, rounds: int = 3) -> str:
    """Two role-playing agents discuss how to design a syllabus for `topic`."""
    transcript: list[str] = []
    opening = (
        f"The learner wants to learn: {topic}. "
        "Let's design a syllabus together. Amina, please start."
    )

    last_message = opening
    for _ in range(rounds):
        # Dr. Amina (practical) speaks
        a_messages = [SystemMessage(content=DESIGNER_A_PROMPT)]
        a_messages += [HumanMessage(content=t) for t in transcript]
        a_messages.append(HumanMessage(content=last_message))
        a_response = await llm.ainvoke(a_messages)
        a_text = extract_text(a_response.content)
        transcript.append(f"Dr. Amina: {a_text}")
        last_message = a_text

        # Dr. Omar (theoretical) replies
        b_messages = [SystemMessage(content=DESIGNER_B_PROMPT)]
        b_messages += [HumanMessage(content=t) for t in transcript]
        b_messages.append(HumanMessage(content=last_message))
        b_response = await llm.ainvoke(b_messages)
        b_text = extract_text(b_response.content)
        transcript.append(f"Dr. Omar: {b_text}")
        last_message = b_text

    return "\n\n".join(transcript)


async def generate_syllabus(topic: str, dialogue: str) -> str:
    """Turn the designer dialogue into a final structured syllabus."""
    messages = [
        SystemMessage(content=SYLLABUS_PROMPT),
        HumanMessage(
            content=(
                f"Learner's topic/goal: {topic}\n\n"
                f"Designer discussion transcript:\n{dialogue}\n\n"
                "Now produce the final syllabus."
            )
        ),
    ]
    response = await llm.ainvoke(messages)
    return extract_text(response.content)


async def instructor_reply(history: list, syllabus: str, user_message: str) -> str:
    """Adaptive instructor turn: given prior chat history + syllabus, teach."""
    system_prompt = INSTRUCTOR_PROMPT_TEMPLATE.format(syllabus=syllabus)
    messages = [SystemMessage(content=system_prompt)] + history + [
        HumanMessage(content=user_message)
    ]
    response = await llm.ainvoke(messages)
    return extract_text(response.content)