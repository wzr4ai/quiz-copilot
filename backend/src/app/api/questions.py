import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.dependencies import get_current_user, require_admin
from app.db import get_session
from app.models import schemas
from app.models.db_models import Bank, FavoriteQuestion, Question as QuestionDB, User
from app.services.ai_service import AIServiceError, ai_service
from app.services.ai_stub import generate_questions_from_text
from app.services.batch_importer import BatchImportService

router = APIRouter(redirect_slashes=False)
logger = logging.getLogger(__name__)


def _to_schema(q: QuestionDB) -> schemas.Question:
    return schemas.Question(
        id=q.id,
        bank_id=q.bank_id,
        type=q.type,
        content=q.content,
        options=[schemas.Option(**opt) for opt in q.options or []],
        standard_answer=q.standard_answer,
        analysis=q.analysis,
    )


def _question_exists(session: Session, payload: schemas.QuestionCreate) -> QuestionDB | None:
    stmt = select(QuestionDB).where(
        QuestionDB.bank_id == payload.bank_id,
        QuestionDB.type == payload.type,
        QuestionDB.content == payload.content,
    )
    candidate = session.exec(stmt).first()
    if not candidate:
        return None
    if payload.type in {"choice_single", "choice_multi"}:
        if candidate.standard_answer.strip().lower() != payload.standard_answer.strip().lower():
            return None
        if len(candidate.options) != len(payload.options):
            return None
        opts_match = all(
            co.get("key") == po.key and (co.get("text") or "").strip() == po.text.strip()
            for co, po in zip(candidate.options, payload.options)
        )
        return candidate if opts_match else None
    if payload.type == "short_answer":
        if candidate.standard_answer.strip().lower() == payload.standard_answer.strip().lower():
            return candidate
    return None


def _create_question(session: Session, payload: schemas.QuestionCreate) -> QuestionDB:
    duplicate = _question_exists(session, payload)
    if duplicate:
        return duplicate
    obj = QuestionDB(
        bank_id=payload.bank_id,
        type=payload.type,
        content=payload.content,
        options=[opt.model_dump() for opt in payload.options or []],
        standard_answer=payload.standard_answer,
        analysis=payload.analysis,
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def _ensure_bank(session: Session, bank_id: int) -> None:
    bank = session.get(Bank, bank_id)
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")


@router.get("/", response_model=list[schemas.Question])
async def list_questions(
    bank_id: int = Query(..., description="题库 ID"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[schemas.Question]:
    _ensure_bank(session, bank_id)
    rows = session.exec(select(QuestionDB).where(QuestionDB.bank_id == bank_id)).all()
    fav_ids = {
        fav.question_id
        for fav in session.exec(
            select(FavoriteQuestion).where(FavoriteQuestion.user_id == current_user.id)
        ).all()
    }
    result: list[schemas.Question] = []
    for q in rows:
        item = _to_schema(q)
        item.is_favorited = q.id in fav_ids
        result.append(item)
    return result


@router.post("/manual", response_model=schemas.Question, status_code=201)
async def create_manual_question(
    payload: schemas.ManualQuestionRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> schemas.Question:
    _ensure_bank(session, payload.bank_id)
    created = _create_question(session, payload)
    return _to_schema(created)


@router.put("/{question_id}", response_model=schemas.Question)
async def update_question(
    question_id: int,
    payload: schemas.QuestionUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> schemas.Question:
    question = session.get(QuestionDB, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    update_data = payload.model_dump(exclude_none=True)
    if "options" in update_data and update_data["options"] is not None:
        normalized_opts = []
        for opt in update_data["options"]:
            if hasattr(opt, "model_dump"):
                normalized_opts.append(opt.model_dump())
            elif isinstance(opt, dict):
                normalized_opts.append({"key": opt.get("key"), "text": opt.get("text")})
        update_data["options"] = normalized_opts
    for field, value in update_data.items():
        setattr(question, field, value)
    session.add(question)
    session.commit()
    session.refresh(question)
    return _to_schema(question)


@router.delete("/{question_id}", status_code=204)
async def delete_question(
    question_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> None:
    question = session.get(QuestionDB, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    session.delete(question)
    session.commit()
    return None


@router.post("/ai/text-to-quiz", response_model=list[schemas.Question])
async def text_to_quiz(
    payload: schemas.AIQuizRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> list[schemas.Question]:
    _ensure_bank(session, payload.bank_id)
    created: list[QuestionDB] = []
    for question_payload in generate_questions_from_text(payload.text, payload.bank_id):
        created.append(_create_question(session, question_payload))
    return [_to_schema(q) for q in created]


@router.post("/ai/image-to-quiz", response_model=list[schemas.Question])
async def image_to_quiz(
    payload: schemas.AIImageQuizRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> list[schemas.Question]:
    _ensure_bank(session, payload.bank_id)
    created: list[QuestionDB] = []
    try:
        generated = await ai_service.generate_questions_from_image(
            image_base64=payload.image_base64, bank_id=payload.bank_id
        )
    except AIServiceError as exc:
        logger.error("Gemini 调用失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    for question_payload in generated:
        created.append(_create_question(session, question_payload))
    return [_to_schema(q) for q in created]


@router.get("/favorites", response_model=list[schemas.Question])
async def list_favorite_questions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[schemas.Question]:
    favorites = session.exec(
        select(QuestionDB)
        .join(FavoriteQuestion, FavoriteQuestion.question_id == QuestionDB.id)
        .where(FavoriteQuestion.user_id == current_user.id)
    ).all()
    result: list[schemas.Question] = []
    for q in favorites:
        item = _to_schema(q)
        item.is_favorited = True
        result.append(item)
    return result


@router.post("/{question_id}/favorite", status_code=204)
async def add_favorite_question(
    question_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    question = session.get(QuestionDB, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    exists = session.exec(
        select(FavoriteQuestion).where(
            FavoriteQuestion.user_id == current_user.id, FavoriteQuestion.question_id == question_id
        )
    ).first()
    if not exists:
        session.add(FavoriteQuestion(user_id=current_user.id, question_id=question_id))
        session.commit()
    return None


@router.delete("/{question_id}/favorite", status_code=204)
async def remove_favorite_question(
    question_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    favorite = session.exec(
        select(FavoriteQuestion).where(
            FavoriteQuestion.user_id == current_user.id, FavoriteQuestion.question_id == question_id
        )
    ).first()
    if favorite:
        session.delete(favorite)
        session.commit()
    return None

@router.post("/ai/batch-import", response_model=schemas.BatchImportResponse)
async def batch_import(
    payload: schemas.BatchImportRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> schemas.BatchImportResponse:
    _ensure_bank(session, payload.bank_id)
    importer = BatchImportService(session=session, ai=ai_service)
    try:
        return await importer.import_directory(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
