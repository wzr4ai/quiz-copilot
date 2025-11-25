from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, banks, questions, study
from app.core.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="SmartQuiz API draft",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    application.include_router(banks.router, prefix="/api/v1/banks", tags=["Banks"])
    application.include_router(questions.router, prefix="/api/v1/questions", tags=["Questions"])
    application.include_router(study.router, prefix="/api/v1/study", tags=["Study"])

    @application.get("/health", tags=["Health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
