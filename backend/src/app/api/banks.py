from fastapi import APIRouter, HTTPException

from app.models.schemas import Bank, BankCreate, BankUpdate
from app.services.in_memory_store import store

router = APIRouter()


@router.get("/", response_model=list[Bank])
async def list_banks() -> list[Bank]:
    return store.list_banks()


@router.post("/", response_model=Bank, status_code=201)
async def create_bank(payload: BankCreate) -> Bank:
    return store.create_bank(payload)


@router.put("/{bank_id}", response_model=Bank)
async def update_bank(bank_id: int, payload: BankUpdate) -> Bank:
    try:
        return store.update_bank(bank_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Bank not found") from None


@router.delete("/{bank_id}", status_code=204)
async def delete_bank(bank_id: int) -> None:
    if bank_id not in store.banks:
        raise HTTPException(status_code=404, detail="Bank not found")
    store.delete_bank(bank_id)
    return None
