"""
Router for the /plan endpoint.
Uses centralized DI from app.dependencies (eve-core pattern).
"""

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_reasoning_engine_dep
from app.models.schemas import ErrorResponse, PlanRequest, PlanResponse
from app.services.reasoning import ReasoningEngine

router = APIRouter(tags=["Course Planning"])


@router.post(
    "/plan",
    response_model=PlanResponse,
    responses={
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Generate a next-term course plan",
    description=(
        "Suggests courses a student is eligible to take next term "
        "based on prerequisites and their completed coursework."
    ),
)
async def generate_plan(
    request: PlanRequest,
    engine: ReasoningEngine = Depends(get_reasoning_engine_dep),
) -> PlanResponse:
    """Generate next-term course suggestions."""
    try:
        return engine.plan(
            completed_courses=request.completed_courses,
            max_courses=request.max_courses,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
