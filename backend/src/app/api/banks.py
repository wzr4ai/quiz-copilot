from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.dependencies import get_current_user, require_admin
from app.db import get_session
from app.models import schemas
from app.models.db_models import Bank, FavoriteBank, User

router = APIRouter()


def _to_schema(bank: Bank) -> schemas.Bank:
    return schemas.Bank(
        id=bank.id,
        title=bank.title,
        description=bank.description,
        is_public=bank.is_public,
    )


@router.get("/", response_model=list[schemas.Bank])
async def list_banks(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[schemas.Bank]:
    banks = session.exec(select(Bank)).all()
    return [_to_schema(b) for b in banks]


@router.get("/favorites", response_model=list[schemas.Bank])
async def list_favorites(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> list[schemas.Bank]:
    joins = (
        session.exec(
            select(Bank)
            .join(FavoriteBank, FavoriteBank.bank_id == Bank.id)
            .where(FavoriteBank.user_id == current_user.id)
        ).all()
    )
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
    session.delete(bank)
    session.commit()
    return None
