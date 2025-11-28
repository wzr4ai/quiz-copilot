import random
from collections import defaultdict

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.dependencies import get_current_user
from app.db import get_session
from app.models import schemas
from app.models.db_models import Bank, FavoriteQuestion, Question as QuestionDB, StudySession, User, WrongRecord

router = APIRouter(redirect_slashes=False)


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


def _wrong_question_ids(session: Session, user_id: int) -> set[int]:
    records = (
        session.exec(
            select(WrongRecord)
            .where(WrongRecord.user_id == user_id)
            .order_by(WrongRecord.question_id, WrongRecord.created_at.desc())
        ).all()
    )
    grouped: dict[int, list[WrongRecord]] = defaultdict(list)
    for rec in records:
        grouped[rec.question_id].append(rec)

    wrong_ids: set[int] = set()
    for qid, recs in grouped.items():
        consecutive_correct = 0
        ever_wrong = False
        for rec in recs:
            if rec.is_correct:
                consecutive_correct += 1
            else:
                ever_wrong = True
                break
        if ever_wrong:
            if consecutive_correct < 3:
                wrong_ids.add(qid)
    return wrong_ids


def _collect_wrong_summaries(session: Session, user_id: int) -> list[schemas.WrongQuestionSummary]:
    records = (
        session.exec(
            select(WrongRecord)
            .where(WrongRecord.user_id == user_id)
            .order_by(WrongRecord.question_id, WrongRecord.created_at.desc())
        ).all()
    )
    latest: dict[int, WrongRecord] = {}
    for rec in records:
        if rec.question_id not in latest:
            latest[rec.question_id] = rec

    wrong_ids = _wrong_question_ids(session, user_id)
    summaries: list[schemas.WrongQuestionSummary] = []
    for qid in wrong_ids:
        record = latest.get(qid)
        question = session.get(QuestionDB, qid)
        if not question or not record:
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


@router.post("/record", response_model=dict)
async def record_answer(
    payload: schemas.SubmitAnswer,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    question = session.get(QuestionDB, payload.question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    raw_answer = payload.answer.strip()
    normalized_answer = _normalize_answer(raw_answer, question.type)
    normalized_standard = _normalize_answer(question.standard_answer.strip(), question.type)
    is_correct = normalized_answer == normalized_standard and normalized_standard != ""

    record = WrongRecord(
        user_id=current_user.id,
        question_id=question.id,
        user_answer=raw_answer,
        correct_answer=question.standard_answer.strip(),
        is_correct=is_correct,
    )
    session.add(record)
    session.commit()

    return {"is_correct": is_correct}


def _normalize_answer(val: str, qtype: str) -> str:
    if qtype == "choice_multi":
        parts = [p.strip().upper() for p in val.replace(" ", ",").split(",") if p.strip()]
        parts.sort()
        return ",".join(parts)
    return val.strip().upper()


@router.get("/session/start", response_model=schemas.StartSessionResponse)
async def start_session(
    bank_id: int | None = Query(None, description="题库 ID"),
    mode: str = Query(
        "random", description="练习模式：random / ordered / wrong / favorite / memorize*"
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> schemas.StartSessionResponse:
    selection_mode = mode
    is_memorize = mode.startswith("memorize")
    if is_memorize:
        if "wrong" in mode:
            selection_mode = "wrong"
        elif "favorite" in mode:
            selection_mode = "favorite"
        else:
            selection_mode = "ordered"

    if selection_mode != "favorite":
        if bank_id is None and selection_mode != "wrong":
            raise HTTPException(status_code=400, detail="bank_id is required for this mode")
        if bank_id is not None:
            _ensure_bank(session, bank_id)
        query = select(QuestionDB)
        if bank_id is not None:
            query = query.where(QuestionDB.bank_id == bank_id)
        questions = session.exec(query).all()
    else:
        fav_query = select(QuestionDB).join(FavoriteQuestion, FavoriteQuestion.question_id == QuestionDB.id).where(
            FavoriteQuestion.user_id == current_user.id
        )
        if bank_id:
            fav_query = fav_query.where(QuestionDB.bank_id == bank_id)
        questions = session.exec(fav_query).all()

    if selection_mode == "wrong":
        wrong_ids = _wrong_question_ids(session, current_user.id)
        questions = [q for q in questions if q.id in wrong_ids]

    if selection_mode == "random":
        random.shuffle(questions)
    else:
        questions.sort(key=lambda x: x.id)

    fav_ids = {
        fav.question_id
        for fav in session.exec(
            select(FavoriteQuestion).where(FavoriteQuestion.user_id == current_user.id)
        ).all()
    }
    study_questions: list[schemas.StudyQuestion] = []
    for q in questions:
        base = _to_study_question(q).model_dump(exclude_none=True, exclude_defaults=True)
        base.update(
            standard_answer=q.standard_answer,
            analysis=q.analysis,
            is_favorited=q.id in fav_ids,
        )
        study_questions.append(schemas.StudyQuestion(**base))
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

    answers_payload = []
    bank_id = None
    for answer in payload.answers:
        question = session.get(QuestionDB, answer.question_id)
        if question is None:
            raise HTTPException(status_code=404, detail=f"Question {answer.question_id} not found")
        bank_id = bank_id or question.bank_id
        raw_answer = answer.answer.strip()
        raw_standard = question.standard_answer.strip()

        normalized_answer = _normalize_answer(raw_answer, question.type)
        normalized_standard = _normalize_answer(raw_standard, question.type)
        is_correct = normalized_answer == normalized_standard and normalized_standard != ""
        if is_correct:
            correct_count += 1

        record = WrongRecord(
            user_id=current_user.id,
            question_id=question.id,
            user_answer=raw_answer,
            correct_answer=raw_standard,
            is_correct=is_correct,
        )
        session.add(record)
        answers_payload.append(record)

    # persist streak logic via wrong records evaluation
    session.commit()
    wrong_items = _collect_wrong_summaries(session, current_user.id)

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

    wrong_items = _collect_wrong_summaries(session, current_user.id)

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
    return _collect_wrong_summaries(session, current_user.id)
