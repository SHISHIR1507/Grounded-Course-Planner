"""
Router for the /ask endpoint.
Uses centralized DI from app.dependencies (eve-core pattern).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_reasoning_engine_dep
from app.models.schemas import AskRequest, AskResponse, ClarifyResponse, ErrorResponse
from app.services.reasoning import ReasoningEngine

router = APIRouter(tags=["Course Planning"])


@router.post(
    "/ask",
    response_model=AskResponse | ClarifyResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Ask a course-related question",
    description=(
        "Check prerequisites, course eligibility, or get grounded answers "
        "from the CS catalog. Returns clarifying questions if info is missing."
    ),
)
async def ask_question(
    request: AskRequest,
    engine: ReasoningEngine = Depends(get_reasoning_engine_dep),
) -> AskResponse | ClarifyResponse:
    """Handle student questions with RAG reasoning."""
    try:
        return engine.ask(
            question=request.question,
            completed_courses=request.completed_courses,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
