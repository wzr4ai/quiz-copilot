from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db import get_session
from app.models.db_models import User

router = APIRouter()


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str | None = None  # default user; admin creation should be controlled externally


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, session: Session = Depends(get_session)) -> TokenResponse:
    existing = session.exec(select(User).where(User.username == payload.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户已存在")

    role = payload.role if payload.role in {"admin", "user"} else "user"
    user = User(
        username=payload.username,
        hashed_password=get_password_hash(payload.password),
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)
) -> TokenResponse:
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user.username, "role": user.role})
    return TokenResponse(access_token=token, username=user.username, role=user.role)
