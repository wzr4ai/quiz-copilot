from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class LoginRequest(BaseModel):
    code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    """
    Draft login endpoint.

    In production this will exchange the WeChat `code` for an openid and sign a JWT.
    """
    dummy_token = f"mock-token-for-{payload.code}"
    return TokenResponse(access_token=dummy_token)
