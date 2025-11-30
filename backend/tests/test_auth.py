import asyncio

import pytest
from fastapi import HTTPException

from app.api.auth import RegisterRequest, register
from app.core.config import settings


def test_register_blocked_in_dev_env():
    payload = RegisterRequest(username="dev_user", password="strongpassword123")
    original_env = settings.app_env
    settings.app_env = "dev"

    try:
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(register(payload, session=None))  # type: ignore[arg-type]
    finally:
        settings.app_env = original_env

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "当前环境不允许注册新用户"
