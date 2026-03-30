"""
Query rewriter service — rewrites ambiguous or context-dependent
queries into standalone, self-contained questions before retrieval.

Adapted from eve-core's QueryRewriterService pattern.
For course planning, this handles cases like:
  "Can I take it?" → "Can I take CS 340 given prerequisites CS 128 and CS 225?"
"""

import json
import re

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import Settings


REWRITE_PROMPT = """\
You are a query rewriting assistant for a university course planning system.

Your job: Rewrite the user's question into a standalone, clear, and unambiguous
question that can be understood without seeing previous conversation history.

Rules:
- If the current question is already clear and complete, return it UNCHANGED.
- If the question contains vague references like "it", "that class", "this one",
  replace them with the specific course codes or concepts they likely refer to.
- Preserve the original intent.
- Do NOT add information or assumptions not present in the question.
- Do NOT answer the question.

Also decide: does this question require course catalog information to answer?
- Set needs_catalog to true if it's about prerequisites, eligibility, course
  content, or course planning.
- Set needs_catalog to false if it's a general greeting or off-topic.

Current user question:
"{question}"

Completed courses provided: {completed_courses}

Respond STRICTLY in valid JSON:
{{
  "rewritten_query": "<standalone rewritten question>",
  "needs_catalog": true or false
}}
"""


class QueryRewriterService:
    """Rewrites queries for improved retrieval quality."""

    def __init__(self, settings: Settings) -> None:
        self.llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0.0,
            openai_api_key=settings.openai_api_key,
        )

    def _clean_json_output(self, text: str) -> str:
        """Strip markdown code fences from LLM JSON output."""
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()
        return text

    def rewrite(
        self,
        question: str,
        completed_courses: list[str] | None = None,
    ) -> dict:
        """
        Rewrite the user's question for better retrieval.

        Returns:
            {
                "rewritten_query": str,
                "needs_catalog": bool
            }
        """
        courses_str = ", ".join(completed_courses) if completed_courses else "None provided"
        prompt = REWRITE_PROMPT.format(
            question=question,
            completed_courses=courses_str,
        )

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            cleaned = self._clean_json_output(response.content)
            result = json.loads(cleaned)

            return {
                "rewritten_query": result.get("rewritten_query", question),
                "needs_catalog": result.get("needs_catalog", True),
            }
        except Exception:
            # Fallback: use original query
            return {
                "rewritten_query": question,
                "needs_catalog": True,
            }
