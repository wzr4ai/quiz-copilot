from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    StartSessionResponse,
    StudyQuestion,
    SubmitRequest,
    SubmitResult,
    WrongQuestionSummary,
)
from app.services.in_memory_store import store

router = APIRouter()


@router.get("/session/start", response_model=StartSessionResponse)
async def start_session(
    bank_id: int = Query(..., description="题库 ID"),
    mode: str = Query("random", description="练习模式：random / ordered / wrong"),
) -> StartSessionResponse:
    if bank_id not in store.banks:
        raise HTTPException(status_code=404, detail="Bank not found")
    questions = store.pick_questions_for_session(bank_id, mode=mode)
    study_questions = [
        StudyQuestion(id=q.id, content=q.content, type=q.type, options=q.options) for q in questions
    ]
    return StartSessionResponse(session_id=f"session-{bank_id}-{mode}", questions=study_questions)


@router.post("/submit", response_model=SubmitResult)
async def submit(payload: SubmitRequest) -> SubmitResult:
    correct_count = 0
    wrong_items: list[WrongQuestionSummary] = []
    for answer in payload.answers:
        question = store.get_question(answer.question_id)
        if question is None:
            raise HTTPException(status_code=404, detail=f"Question {answer.question_id} not found")
        normalized_answer = answer.answer.strip()
        normalized_standard = question.standard_answer.strip()
        is_correct = normalized_answer.lower() == normalized_standard.lower()
        if is_correct:
            correct_count += 1
        wrong_record = store.record_answer(question, normalized_answer, is_correct)
        if wrong_record:
            wrong_items.append(wrong_record)

    total = len(payload.answers)
    score = round((correct_count / total) * 100) if total else 0
    return SubmitResult(
        correct_count=correct_count,
        total=total,
        score=score,
        wrong_questions=wrong_items,
    )


@router.get("/wrong", response_model=list[WrongQuestionSummary])
async def list_wrong_questions() -> list[WrongQuestionSummary]:
    return store.list_wrong_records()
