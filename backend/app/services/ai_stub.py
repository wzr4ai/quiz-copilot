"""Lightweight AI stub that fabricates quiz questions for demos."""

from textwrap import shorten

from app.models.schemas import Option, QuestionCreate


def _safe_snippet(text: str) -> str:
    return shorten(text.strip().replace("\n", " "), width=80, placeholder="...")


def generate_questions_from_text(text: str, bank_id: int) -> list[QuestionCreate]:
    snippet = _safe_snippet(text) or "这是一段待识别的学习资料"
    choice_question = QuestionCreate(
        bank_id=bank_id,
        type="choice_single",
        content=f"基于材料，下列描述最贴近原文含义？\n{snippet}",
        options=[
            Option(key="A", text="概括核心观点"),
            Option(key="B", text="与材料无关的陈述"),
            Option(key="C", text="材料的细节例子"),
            Option(key="D", text="相反立场"),
        ],
        standard_answer="A",
        analysis="聚焦材料中的核心主张或结论。",
    )

    short_answer = QuestionCreate(
        bank_id=bank_id,
        type="short_answer",
        content="用一句话总结材料的要点？",
        options=[],
        standard_answer="突出关键词与结论即可。",
        analysis="回答需包含材料中提到的关键要素与结论。",
    )
    return [choice_question, short_answer]


def generate_questions_from_image(image_base64: str, bank_id: int) -> list[QuestionCreate]:
    marker = image_base64[:16] if image_base64 else "image"
    return [
        QuestionCreate(
            bank_id=bank_id,
            type="choice_single",
            content=f"图片({marker}...)识别：最可能的考点是什么？",
            options=[
                Option(key="A", text="选择题示例"),
                Option(key="B", text="解答题示例"),
                Option(key="C", text="与试卷无关"),
            ],
            standard_answer="A",
            analysis="示例数据，后续接入真实 OCR 与解析。",
        )
    ]
