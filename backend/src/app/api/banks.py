from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete
from sqlmodel import Session, select

from app.dependencies import get_current_user, require_admin
from app.db import get_session
from app.models import schemas
from app.models.db_models import (
    Bank,
    FavoriteBank,
    FavoriteQuestion,
    Question,
    StudySession,
    User,
    WrongRecord,
)

router = APIRouter(redirect_slashes=False)


def _to_schema(bank: Bank) -> schemas.Bank:
    return schemas.Bank(
        id=bank.id,
        title=bank.title,
        description=bank.description,
        is_public=bank.is_public,
    )


def _ensure_readable(bank: Bank, user: User) -> None:
    if user.role != "admin" and not bank.is_public:
        raise HTTPException(status_code=403, detail="无权访问非公开题库")


@router.get("/", response_model=list[schemas.Bank])
async def list_banks(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[schemas.Bank]:
    stmt = select(Bank)
    if current_user.role != "admin":
        stmt = stmt.where(Bank.is_public.is_(True))
    banks = session.exec(stmt).all()
    return [_to_schema(b) for b in banks]


@router.get("/favorites", response_model=list[schemas.Bank])
async def list_favorites(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> list[schemas.Bank]:
    stmt = (
        select(Bank)
        .join(FavoriteBank, FavoriteBank.bank_id == Bank.id)
        .where(FavoriteBank.user_id == current_user.id)
    )
    if current_user.role != "admin":
        stmt = stmt.where(Bank.is_public.is_(True))
    joins = session.exec(stmt).all()
    return [_to_schema(b) for b in joins]


@router.post("/{bank_id}/favorite", status_code=204)
async def add_favorite(
    bank_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    bank = session.get(Bank, bank_id)
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    _ensure_readable(bank, current_user)
    exists = session.exec(
        select(FavoriteBank).where(
            FavoriteBank.user_id == current_user.id, FavoriteBank.bank_id == bank_id
        )
    ).first()
    if not exists:
        session.add(FavoriteBank(user_id=current_user.id, bank_id=bank_id))
        session.commit()
    return None


@router.delete("/{bank_id}/favorite", status_code=204)
async def remove_favorite(
    bank_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    fav = session.exec(
        select(FavoriteBank).where(
            FavoriteBank.user_id == current_user.id, FavoriteBank.bank_id == bank_id
        )
    ).first()
    if fav:
        bank = session.get(Bank, bank_id)
        if bank:
            _ensure_readable(bank, current_user)
    if fav:
        session.delete(fav)
        session.commit()
    return None


@router.post("/", response_model=schemas.Bank, status_code=201)
async def create_bank(
    payload: schemas.BankCreate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> schemas.Bank:
    bank = Bank(
        title=payload.title,
        description=payload.description,
        is_public=payload.is_public,
        created_by=admin.id,
    )
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return _to_schema(bank)


@router.put("/{bank_id}", response_model=schemas.Bank)
async def update_bank(
    bank_id: int,
    payload: schemas.BankUpdate,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> schemas.Bank:
    bank = session.get(Bank, bank_id)
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(bank, field, value)
    session.add(bank)
    session.commit()
    session.refresh(bank)
    return _to_schema(bank)


@router.delete("/{bank_id}", status_code=204)
async def delete_bank(
    bank_id: int,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> None:
    bank = session.get(Bank, bank_id)
    if not bank:
        raise HTTPException(status_code=404, detail="Bank not found")
    # delete dependent records: favorites (bank/questions), wrong records, study sessions, questions
    # remove study sessions first to avoid FK constraint on bank_id
    session.exec(delete(StudySession).where(StudySession.bank_id == bank_id))

    question_ids = [
        q.id for q in session.exec(select(Question).where(Question.bank_id == bank_id)).all() if q.id
    ]
    if question_ids:
        session.exec(delete(FavoriteQuestion).where(FavoriteQuestion.question_id.in_(question_ids)))
        session.exec(delete(WrongRecord).where(WrongRecord.question_id.in_(question_ids)))
        session.exec(delete(Question).where(Question.id.in_(question_ids)))

    session.exec(delete(FavoriteBank).where(FavoriteBank.bank_id == bank_id))

    session.delete(bank)
    session.commit()
    return None


@router.post("/merge", response_model=schemas.BankMergeResponse, status_code=201)
async def merge_banks(
    payload: schemas.BankMergeRequest,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> schemas.BankMergeResponse:
    source_ids = list(dict.fromkeys(payload.source_bank_ids))
    if len(source_ids) < 2:
        raise HTTPException(status_code=400, detail="请选择至少两个要合并的题库")
    banks = session.exec(select(Bank).where(Bank.id.in_(source_ids))).all()
    found_ids = {b.id for b in banks if b.id is not None}
    missing = [bid for bid in source_ids if bid not in found_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"题库不存在: {missing}")

    new_bank = Bank(
        title=payload.title,
        description=payload.description,
        is_public=payload.is_public,
        created_by=admin.id,
    )
    session.add(new_bank)
    session.commit()
    session.refresh(new_bank)

    merged_count = 0
    for bank_id in source_ids:
        questions = session.exec(select(Question).where(Question.bank_id == bank_id)).all()
        for q in questions:
            cloned_options = []
            for opt in q.options or []:
                if isinstance(opt, dict):
                    cloned_options.append({**opt})
                else:
                    cloned_options.append(opt)
            new_question = Question(
                bank_id=new_bank.id,
                type=q.type,
                content=q.content,
                options=cloned_options,
                standard_answer=q.standard_answer,
                analysis=q.analysis,
            )
            session.add(new_question)
            merged_count += 1
    session.commit()

    return schemas.BankMergeResponse(
        bank=_to_schema(new_bank),
        merged_questions=merged_count,
        source_bank_ids=source_ids,
    )
