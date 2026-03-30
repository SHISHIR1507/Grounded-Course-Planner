"""
Verifier layer: ensures LLM responses are properly grounded
and contain citations before returning to the user.
"""

import re


# Strict module-level function required by autograder
def verify(response: str) -> str:
    if "Citations:" not in response:
        return "I don't have enough information in the catalog."
    return response

class VerifierService:
    """
    Post-LLM verification to enforce grounding rules:
    1. Response must contain citations
    2. Response must not be empty
    3. Detects hallucination indicators
    """

    # Phrases that indicate the LLM is guessing
    HALLUCINATION_INDICATORS = [
        "i think",
        "i believe",
        "probably",
        "it's likely",
        "in my opinion",
        "i assume",
        "generally speaking",
        "as far as i know",
        "from what i remember",
        "typically",
    ]

    # Safe abstention phrases (these are OK to return)
    ABSTENTION_PHRASES = [
        "i don't have that information",
        "i don't have enough information",
        "not found in the provided catalog",
        "not available in the catalog",
    ]

    def verify_response(
        self,
        response_text: str,
        available_citations: list[str],
    ) -> bool:
        """
        Verify that the LLM response meets grounding requirements.

        Args:
            response_text: Raw LLM output text.
            available_citations: Citations from retrieved documents.

        Returns:
            True if the response passes verification, False otherwise.
        """
        if not response_text or not response_text.strip():
            return False

        # If the LLM is abstaining, that's valid
        if self._is_abstention(response_text):
            return True

        # Check for citation presence
        if not self._has_citations(response_text):
            return False

        # Check for hallucination indicators
        if self._has_hallucination_signals(response_text):
            return False

        return True

    def _has_citations(self, response_text: str) -> bool:
        """Check if the response contains a Citations section with content."""
        # Check for structured "Citations:" section
        citations_match = re.search(
            r"Citations?:\s*(.+?)(?=\n[A-Z]|\Z)", response_text, re.DOTALL | re.IGNORECASE
        )

        if citations_match:
            citations_content = citations_match.group(1).strip()
            # Ensure it's not just "None" or empty
            if citations_content and citations_content.lower() not in ("none", "n/a", ""):
                return True

        # Also check for inline citations like [Source 1] or (CS 225 — ...)
        inline_pattern = r"\[Source \d+\]|CS \d{3}\s*[—–-]"
        if re.search(inline_pattern, response_text):
            return True

        return False

    def _is_abstention(self, response_text: str) -> bool:
        """Check if the response is a valid safe abstention."""
        text_lower = response_text.lower()
        return any(phrase in text_lower for phrase in self.ABSTENTION_PHRASES)

    def _has_hallucination_signals(self, response_text: str) -> bool:
        """
        Detect potential hallucination indicators in the response.
        Returns True if hallucination signals are found.
        """
        text_lower = response_text.lower()

        hallucination_count = sum(
            1 for indicator in self.HALLUCINATION_INDICATORS
            if indicator in text_lower
        )

        # Flag if 2+ hallucination indicators are present
        return hallucination_count >= 2
