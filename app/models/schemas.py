"""
Pydantic schemas for request/response validation.
Adopts eve-core patterns: SourceChunk with score, structured response metadata.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Request Schemas ────────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    """Request body for the /ask endpoint."""

    question: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="The student's course-related question.",
        examples=["Can I take CS 341?"],
    )
    completed_courses: list[str] = Field(
        default_factory=list,
        description="List of courses the student has already completed.",
        examples=[["CS 101", "CS 124", "CS 128", "CS 225"]],
    )


class PlanRequest(BaseModel):
    """Request body for the /plan endpoint."""

    completed_courses: list[str] = Field(
        ...,
        min_length=1,
        description="List of courses the student has already completed.",
        examples=[["CS 124", "CS 128", "CS 173", "CS 225"]],
    )
    max_courses: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of courses to suggest.",
    )


# ── Source / Citation Schemas ──────────────────────────────────────────────────


class SourceChunk(BaseModel):
    """
    A single retrieved chunk with relevance score.
    Pattern from eve-core: always return chunk metadata for transparency.
    """

    course: str = Field(..., description="Course code, e.g. 'CS 340'")
    section: str | None = Field(default=None, description="Catalog section identifier")
    source: str | None = Field(default=None, description="Source document name")
    content: str = Field(..., description="Retrieved chunk text")
    score: float | None = Field(default=None, description="Similarity score (lower = better for FAISS L2)")
    metadata: dict[str, Any] | None = Field(default=None, description="Raw metadata dict")


# ── Response Schemas ───────────────────────────────────────────────────────────


class AskResponse(BaseModel):
    """Structured response for the /ask endpoint."""

    decision: str = Field(..., description="Eligibility decision or direct answer.")
    why: str = Field(..., description="Reasoning based on catalog data.")
    citations: list[str] = Field(..., description="Source references from the catalog.")
    next_step: str = Field(..., description="Actionable recommendation.")
    assumptions: str = Field(..., description="Assumptions made, or 'None'.")
    sources: list[SourceChunk] = Field(
        default_factory=list,
        description="Raw retrieved chunks with scores for transparency.",
    )
    latency_ms: int | None = Field(default=None, description="LLM call latency in ms.")
    rewritten_query: str | None = Field(
        default=None,
        description="The query after rewriting (if different from original).",
    )


class PlanResponse(BaseModel):
    """Structured response for the /plan endpoint."""

    suggested_courses: list[dict] = Field(
        ...,
        description="List of suggested courses with eligibility and citations.",
    )
    risks_assumptions: str = Field(
        ...,
        description="Risks or assumptions, or 'None'.",
    )
    sources: list[SourceChunk] = Field(
        default_factory=list,
        description="Raw retrieved chunks with scores.",
    )
    latency_ms: int | None = Field(default=None, description="LLM call latency in ms.")


class ClarifyResponse(BaseModel):
    """Response when clarifying questions are needed."""

    clarifying_questions: list[str] = Field(
        ...,
        description="1–3 clarifying questions for the student.",
    )


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str | None = None
