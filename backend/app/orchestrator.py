"""
Router Agent (Orchestrator)
============================
هذا الوكيل مسؤول عن قرار "أي وكيل متخصص يستقبل رسالة المستخدم؟" — بدل
ما يختار المستخدم يدوياً من قائمة، هذا الوكيل يحلل نية الرسالة الأولى
ويوجّهها تلقائياً إلى:
- Assignment Planner: لو الرسالة عن تخطيط/جدولة واجب
- AI Instructor: لو الرسالة عن تعلّم موضوع جديد
"""

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

load_dotenv()

# نموذج مستقل وخفيف مخصص للتصنيف فقط (temperature=0 عشان يكون حاسم وثابت)
router_llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0,
)

ROUTER_PROMPT = """You are a routing classifier for a student assistant app
with two specialized agents:

1. PLANNER — helps students plan and schedule assignments. Triggered by
   messages that provide or ask about: an assignment name, a deadline, a
   difficulty level, an estimated completion time, or a general request to
   organize/schedule/plan academic work.

2. INSTRUCTOR — helps students learn a new topic through an interactive
   syllabus and adaptive teaching. Triggered by messages expressing a
   desire to learn, study, understand, or be taught a subject or skill.

Respond with EXACTLY one word, nothing else:
PLANNER
or
INSTRUCTOR
or
UNCLEAR   (only if the message truly doesn't fit either, e.g. small talk,
           or something entirely unrelated)

User's message:
\"\"\"{message}\"\"\"
"""


def _extract_text(content) -> str:
    """يستخرج النص الصافي من رد الموديل، حتى لو رجع كـ list of content blocks."""
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    return str(content).strip()


async def classify_intent(message: str) -> str:
    """يرجع 'planner' أو 'instructor' أو 'unclear'."""
    prompt = ROUTER_PROMPT.format(message=message)
    response = await router_llm.ainvoke([HumanMessage(content=prompt)])
    text = _extract_text(response.content).upper()

    if "PLANNER" in text:
        return "planner"
    if "INSTRUCTOR" in text:
        return "instructor"
    return "unclear"