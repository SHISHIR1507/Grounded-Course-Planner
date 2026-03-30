"""
Reasoning engine: orchestrates retrieval → prompt construction → LLM call.
Handles both /ask and /plan flows.

Adopts eve-core patterns:
- Explicit dependency injection (no global singletons)
- Query rewriting before retrieval
- Latency tracking via time.perf_counter()
- Structured source chunks in responses
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import Settings
from app.core.prompts import ASK_SYSTEM_PROMPT, CLARIFY_PROMPT, PLAN_SYSTEM_PROMPT
from app.models.schemas import (
    AskResponse,
    ClarifyResponse,
    PlanResponse,
    SourceChunk,
)
from app.services.retriever import RetrieverService
from app.services.verifier import VerifierService
from app.services.query_rewriter import QueryRewriterService


class ReasoningEngine:
    """
    Core reasoning engine that:
    1. Rewrites queries for better retrieval
    2. Retrieves relevant context from FAISS
    3. Constructs grounded prompts
    4. Calls the LLM
    5. Verifies response integrity
    6. Tracks latency
    """

    def __init__(
        self,
        settings: Settings,
        retriever: RetrieverService,
        verifier: VerifierService,
        query_rewriter: QueryRewriterService,
    ) -> None:
        self.settings = settings
        self.retriever = retriever
        self.verifier = verifier
        self.query_rewriter = query_rewriter
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            openai_api_key=settings.openai_api_key,
        )

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _needs_clarification(self, question: str, completed_courses: list[str]) -> bool:
        """Check if user omitted required info for eligibility questions."""
        eligibility_keywords = [
            "can i take", "eligible", "prerequisite", "prereq",
            "qualify", "ready for", "allowed to",
        ]
        question_lower = question.lower()
        needs_courses = any(kw in question_lower for kw in eligibility_keywords)
        return needs_courses and len(completed_courses) == 0

    def _build_source_chunks(
        self, docs_with_scores: list[tuple[Any, float]]
    ) -> list[SourceChunk]:
        """Convert retriever results into structured SourceChunk objects."""
        chunks: list[SourceChunk] = []
        for doc, score in docs_with_scores:
            meta = doc.metadata
            chunks.append(
                SourceChunk(
                    course=meta.get("course", "Unknown"),
                    section=meta.get("section"),
                    source=meta.get("source"),
                    content=doc.page_content,
                    score=float(score),
                    metadata=meta,
                )
            )
        return chunks

    # ── Main flows ─────────────────────────────────────────────────────────────

    def generate_clarifying_questions(self, question: str) -> ClarifyResponse:
        """Generate 1–3 clarifying questions when required info is missing."""
        prompt = CLARIFY_PROMPT.format(question=question)
        response = self.llm.invoke([HumanMessage(content=prompt)])

        try:
            questions = json.loads(response.content)
            if isinstance(questions, list):
                return ClarifyResponse(clarifying_questions=questions[:3])
        except (json.JSONDecodeError, TypeError):
            pass

        return ClarifyResponse(
            clarifying_questions=[
                "What courses have you completed so far?",
                "Which specific course are you asking about?",
            ]
        )

    def ask(
        self, question: str, completed_courses: list[str]
    ) -> AskResponse | ClarifyResponse:
        """
        Process a student's question through the full RAG pipeline.

        Steps:
        1. Check if clarification is needed
        2. Rewrite query for better retrieval
        3. Retrieve relevant documents (with scores)
        4. Build grounded prompt
        5. Call LLM (track latency)
        6. Verify response has citations
        7. Parse and return structured response
        """
        # Step 1: Check for missing info
        if self._needs_clarification(question, completed_courses):
            return self.generate_clarifying_questions(question)

        # Step 2: Rewrite query
        rewrite_result = self.query_rewriter.rewrite(question, completed_courses)
        search_query = rewrite_result["rewritten_query"]

        # Step 3: Retrieve with scores (eve-core pattern)
        docs_with_scores = self.retriever.retrieve_with_scores(search_query)
        documents = [doc for doc, _ in docs_with_scores]
        source_chunks = self._build_source_chunks(docs_with_scores)

        context = self.retriever.format_context(documents)
        available_citations = self.retriever.extract_citations(documents)

        # Step 4: Build prompt
        completed_str = ", ".join(completed_courses) if completed_courses else "None provided"
        system_prompt = ASK_SYSTEM_PROMPT.format(
            context=context,
            completed_courses=completed_str,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=question),
        ]

        # Step 5: Call LLM with latency tracking (eve-core pattern)
        start = time.perf_counter()
        response = self.llm.invoke(messages)
        latency_ms = int((time.perf_counter() - start) * 1000)
        raw_text = response.content

        # Step 6: Verify citations exist
        if not self.verifier.verify_response(raw_text, available_citations):
            return AskResponse(
                decision="Unable to determine",
                why="I don't have enough information in the catalog.",
                citations=[],
                next_step="Please consult your academic advisor for accurate information.",
                assumptions="The catalog data available did not contain sufficient information.",
                sources=source_chunks,
                latency_ms=latency_ms,
                rewritten_query=search_query if search_query != question else None,
            )

        # Step 7: Parse structured response
        parsed = self._parse_ask_response(raw_text, available_citations)
        parsed.sources = source_chunks
        parsed.latency_ms = latency_ms
        parsed.rewritten_query = search_query if search_query != question else None
        return parsed

    def plan(self, completed_courses: list[str], max_courses: int) -> PlanResponse:
        """
        Generate a next-term course plan.

        Steps:
        1. Build a retrieval query from completed courses
        2. Retrieve relevant catalog entries (with scores)
        3. Build grounded prompt
        4. Call LLM (track latency)
        5. Parse and return structured response
        """
        # Step 1: Build retrieval query
        query = (
            f"What courses can a student take next if they have completed: "
            f"{', '.join(completed_courses)}? "
            f"Consider prerequisites and course sequences."
        )

        # Step 2: Retrieve with scores
        k = min(self.settings.retriever_k + 2, 10)
        docs_with_scores = self.retriever.retrieve_with_scores(query, k=k)
        documents = [doc for doc, _ in docs_with_scores]
        source_chunks = self._build_source_chunks(docs_with_scores)

        context = self.retriever.format_context(documents)
        available_citations = self.retriever.extract_citations(documents)

        # Step 3: Build prompt
        completed_str = ", ".join(completed_courses)
        system_prompt = PLAN_SYSTEM_PROMPT.format(
            context=context,
            completed_courses=completed_str,
            max_courses=max_courses,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"Based on my completed courses ({completed_str}), "
                    f"suggest up to {max_courses} courses I can take next term."
                )
            ),
        ]

        # Step 4: Call LLM with latency tracking
        start = time.perf_counter()
        response = self.llm.invoke(messages)
        latency_ms = int((time.perf_counter() - start) * 1000)
        raw_text = response.content

        # Step 5: Verify and parse
        if not self.verifier.verify_response(raw_text, available_citations):
            return PlanResponse(
                suggested_courses=[],
                risks_assumptions=(
                    "I don't have enough information in the catalog to "
                    "make reliable course recommendations."
                ),
                sources=source_chunks,
                latency_ms=latency_ms,
            )

        parsed = self._parse_plan_response(raw_text)
        parsed.sources = source_chunks
        parsed.latency_ms = latency_ms
        return parsed

    # ── Parsers ────────────────────────────────────────────────────────────────

    def _parse_ask_response(
        self, raw_text: str, fallback_citations: list[str]
    ) -> AskResponse:
        """Parse the LLM's structured text response into an AskResponse."""
        if self.verifier._is_abstention(raw_text):
            return AskResponse(
                decision="Unknown",
                why=raw_text.strip(),
                citations=[],
                next_step="Consult your academic advisor.",
                assumptions="None",
            )

        sections: dict[str, Any] = {
            "decision": "",
            "why": "",
            "citations": [],
            "next_step": "",
            "assumptions": "",
        }

        patterns = {
            "decision": r"Decision:\s*(.+?)(?=\nWhy:|\Z)",
            "why": r"Why:\s*(.+?)(?=\nCitations:|\Z)",
            "citations_raw": r"Citations:\s*(.+?)(?=\nNext Step:|\Z)",
            "next_step": r"Next Step:\s*(.+?)(?=\nAssumptions:|\Z)",
            "assumptions": r"Assumptions:\s*(.+?)(?=\Z)",
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, raw_text, re.DOTALL)
            if match:
                value = match.group(1).strip()
                if key == "citations_raw":
                    citation_lines = [
                        line.strip().lstrip("- •*")
                        for line in value.split("\n")
                        if line.strip()
                    ]
                    sections["citations"] = citation_lines
                else:
                    sections[key] = value

        # Fallback: use retriever citations if LLM didn't produce any
        if not sections["citations"]:
            sections["citations"] = fallback_citations

        return AskResponse(**sections)

    def _parse_plan_response(self, raw_text: str) -> PlanResponse:
        """Parse the LLM's structured text response into a PlanResponse."""
        suggested_courses: list[dict] = []

        course_pattern = r"\d+\.\s*(\S+)\s*[—–-]\s*(.+?)(?=\n\d+\.|\nRisks|$)"
        matches = re.findall(course_pattern, raw_text, re.DOTALL)

        for course_code, block in matches:
            eligibility_match = re.search(
                r"Eligibility:\s*(.+?)(?=\n\s*Citation:|\Z)", block, re.DOTALL
            )
            citation_match = re.search(r"Citation:\s*(.+?)(?=\n|$)", block, re.DOTALL)

            suggested_courses.append(
                {
                    "course": course_code.strip(),
                    "title": block.split("\n")[0].strip() if block else "",
                    "eligibility": (
                        eligibility_match.group(1).strip()
                        if eligibility_match
                        else "See catalog"
                    ),
                    "citation": (
                        citation_match.group(1).strip()
                        if citation_match
                        else "Illinois CS Catalog PDF"
                    ),
                }
            )

        risks_match = re.search(
            r"Risks/Assumptions:\s*(.+?)$", raw_text, re.DOTALL
        )
        risks = risks_match.group(1).strip() if risks_match else "None"

        return PlanResponse(
            suggested_courses=suggested_courses,
            risks_assumptions=risks,
        )
