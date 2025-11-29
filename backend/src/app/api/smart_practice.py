from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.db import get_session
from app.dependencies import get_current_user
from app.models import schemas
from app.models.db_models import User
from app.services import smart_practice_service

router = APIRouter(redirect_slashes=False)


@router.get("/status", response_model=schemas.SmartPracticeStatus)
async def get_status(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> schemas.SmartPracticeStatus:
    return smart_practice_service.get_status(session, current_user)


@router.get("/settings", response_model=schemas.SmartPracticeSettingsResponse | None)
async def get_settings(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> schemas.SmartPracticeSettingsResponse | None:
    settings = smart_practice_service.get_latest_settings(session, current_user.id)
    return settings


@router.put("/settings", response_model=schemas.SmartPracticeSettingsResponse)
async def save_settings(
    payload: schemas.SmartPracticeSettingsPayload,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> schemas.SmartPracticeSettingsResponse:
    return smart_practice_service.save_settings(session, payload, current_user)


@router.post("/session/start", response_model=schemas.SmartPracticeGroup)
async def start_session(
    session: Session = Depends(get_session), current_user: User = Depends(get_current_user)
) -> schemas.SmartPracticeGroup:
    return smart_practice_service.start_session(session, current_user)


@router.get("/session/{session_id}/current", response_model=schemas.SmartPracticeGroup)
async def get_current_group(
    session_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> schemas.SmartPracticeGroup:
    return smart_practice_service.get_current_group(session, session_id, current_user)


@router.post("/session/{session_id}/answer", response_model=schemas.SmartPracticeAnswerResponse)
async def answer_question(
    session_id: str,
    payload: schemas.SmartPracticeAnswerRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> schemas.SmartPracticeAnswerResponse:
    return smart_practice_service.answer_question(session, session_id, payload, current_user)


@router.post("/session/{session_id}/toggle-analysis", response_model=schemas.SmartPracticeStatus)
async def toggle_analysis(
    session_id: str,
    payload: schemas.SmartPracticeToggleRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> schemas.SmartPracticeStatus:
    sp_session = smart_practice_service.toggle_realtime_analysis(session, session_id, payload.realtime_analysis, current_user)
    return smart_practice_service.get_status(session, current_user)


@router.post("/session/{session_id}/next-group", response_model=schemas.SmartPracticeGroup)
async def next_group(
    session_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> schemas.SmartPracticeGroup:
    return smart_practice_service.next_group(session, session_id, current_user)


@router.post("/session/{session_id}/finish", response_model=dict)
async def finish_session(
    session_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    smart_practice_service.finish_session(session, session_id, current_user)
    return {"status": "completed"}


@router.post("/session/{session_id}/feedback", response_model=dict)
async def feedback_and_skip(
    session_id: str,
    payload: schemas.SmartPracticeFeedbackRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    smart_practice_service.feedback_and_skip(session, session_id, payload, current_user)
    return {"status": "ok"}


@router.delete("/session/reset", response_model=dict)
async def reset_session_state(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    smart_practice_service.reset_user_state(session, current_user)
    return {"status": "reset"}
