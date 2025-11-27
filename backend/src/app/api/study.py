import random
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.dependencies import get_current_user
from app.db import get_session
from app.models import schemas
from app.models.db_models import Bank, Question as QuestionDB, StudySession, User, WrongRecord

router = APIRouter()


def _ensure_bank(session: Session, bank_id: int) -> None:
    bank = session.get(Bank, bank_id)
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")


def _to_study_question(q: QuestionDB) -> schemas.StudyQuestion:
    return schemas.StudyQuestion(
        id=q.id, content=q.content, type=q.type, options=[schemas.Option(**opt) for opt in q.options or []]
    )


def _to_question(q: QuestionDB) -> schemas.Question:
    return schemas.Question(
        id=q.id,
        bank_id=q.bank_id,
        type=q.type,
        content=q.content,
        options=[schemas.Option(**opt) for opt in q.options or []],
        standard_answer=q.standard_answer,
        analysis=q.analysis,
    )


@router.get("/session/start", response_model=schemas.StartSessionResponse)
async def start_session(
    bank_id: int = Query(..., description="题库 ID"),
    mode: str = Query("random", description="练习模式：random / ordered / wrong"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> schemas.StartSessionResponse:
    _ensure_bank(session, bank_id)
    query = select(QuestionDB).where(QuestionDB.bank_id == bank_id)
    questions = session.exec(query).all()

    if mode == "wrong":
        wrong_ids = {
            rec.question_id
            for rec in session.exec(
                select(WrongRecord).where(WrongRecord.user_id == current_user.id, WrongRecord.is_correct.is_(False))
            ).all()
        }
        questions = [q for q in questions if q.id in wrong_ids]

    if mode == "random":
        random.shuffle(questions)
    else:
        questions.sort(key=lambda x: x.id)

    study_questions = [_to_study_question(q) for q in questions]
    return schemas.StartSessionResponse(
        session_id=f"session-{bank_id}-{mode}-{current_user.id}", questions=study_questions
    )


@router.post("/submit", response_model=schemas.SubmitResult)
async def submit(
    payload: schemas.SubmitRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> schemas.SubmitResult:
    correct_count = 0
    wrong_items: list[schemas.WrongQuestionSummary] = []

    answers_payload = []
    bank_id = None
    for answer in payload.answers:
        question = session.get(QuestionDB, answer.question_id)
        if question is None:
            raise HTTPException(status_code=404, detail=f"Question {answer.question_id} not found")
        bank_id = bank_id or question.bank_id
        normalized_answer = answer.answer.strip()
        normalized_standard = question.standard_answer.strip()
        is_correct = normalized_answer.lower() == normalized_standard.lower()
        if is_correct:
            correct_count += 1

        record = WrongRecord(
            user_id=current_user.id,
            question_id=question.id,
            user_answer=normalized_answer,
            correct_answer=question.standard_answer,
            is_correct=is_correct,
        )
        session.add(record)
        if not is_correct:
            wrong_items.append(
                schemas.WrongQuestionSummary(
                    question=_to_question(question),
                    user_answer=normalized_answer,
                    correct_answer=question.standard_answer,
                    created_at=record.created_at,
                )
            )
        answers_payload.append(record)

    total = len(payload.answers)
    score = round((correct_count / total) * 100) if total else 0

    session.add(
        StudySession(
            user_id=current_user.id,
            bank_id=bank_id or 0,
            mode=payload.session_id,
            score=score,
            answers=[
                {
                    "question_id": rec.question_id,
                    "user_answer": rec.user_answer,
                    "is_correct": rec.is_correct,
                }
                for rec in answers_payload
            ],
        )
    )
    session.commit()

    return schemas.SubmitResult(
        correct_count=correct_count,
        total=total,
        score=score,
        wrong_questions=wrong_items,
    )


@router.get("/wrong", response_model=list[schemas.WrongQuestionSummary])
async def list_wrong_questions(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[schemas.WrongQuestionSummary]:
    records = session.exec(select(WrongRecord).where(WrongRecord.user_id == current_user.id)).all()
    latest: dict[int, WrongRecord] = {}
    for record in records:
        latest[record.question_id] = record

    summaries: list[schemas.WrongQuestionSummary] = []
    for record in latest.values():
        question = session.get(QuestionDB, record.question_id)
        if not question or record.is_correct:
            continue
        summaries.append(
            schemas.WrongQuestionSummary(
                question=_to_question(question),
                user_answer=record.user_answer,
                correct_answer=record.correct_answer,
                created_at=record.created_at,
            )
        )
    return summaries
