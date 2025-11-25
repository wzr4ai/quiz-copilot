from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import AIImageQuizRequest, AIQuizRequest, ManualQuestionRequest, Question, QuestionUpdate
from app.services.ai_stub import generate_questions_from_image, generate_questions_from_text
from app.services.in_memory_store import store

router = APIRouter()


@router.get("/", response_model=list[Question])
async def list_questions(bank_id: int = Query(..., description="题库 ID")) -> list[Question]:
    return store.list_questions(bank_id=bank_id)


@router.post("/manual", response_model=Question, status_code=201)
async def create_manual_question(payload: ManualQuestionRequest) -> Question:
    if payload.bank_id not in store.banks:
        raise HTTPException(status_code=404, detail="Bank not found")
    return store.create_question(payload)


@router.put("/{question_id}", response_model=Question)
async def update_question(question_id: int, payload: QuestionUpdate) -> Question:
    try:
        return store.update_question(question_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Question not found") from None


@router.post("/ai/text-to-quiz", response_model=list[Question])
async def text_to_quiz(payload: AIQuizRequest) -> list[Question]:
    if payload.bank_id not in store.banks:
        raise HTTPException(status_code=404, detail="Bank not found")
    created: list[Question] = []
    for question_payload in generate_questions_from_text(payload.text, payload.bank_id):
        created.append(store.create_question(question_payload))
    return created


@router.post("/ai/image-to-quiz", response_model=list[Question])
async def image_to_quiz(payload: AIImageQuizRequest) -> list[Question]:
    if payload.bank_id not in store.banks:
        raise HTTPException(status_code=404, detail="Bank not found")
    created: list[Question] = []
    for question_payload in generate_questions_from_image(payload.image_base64, payload.bank_id):
        created.append(store.create_question(question_payload))
    return created
