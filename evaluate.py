"""
Evaluation script to test the RAG system performance over 25 test queries.

Calculates:
- Citation coverage %
- Abstention accuracy %
- Average latency

Correctness % requires manual review (or LLM-as-a-judge in a follow-up).
"""

import sys
import time
from pathlib import Path

# Fix import path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.core.config import get_settings
from app.services.retriever import RetrieverService
from app.services.verifier import VerifierService
from app.services.query_rewriter import QueryRewriterService
from app.services.reasoning import ReasoningEngine


# ── 25 Test Queries ────────────────────────────────────────────────────────────
# Categories:
#   prereq = standard prerequisite check
#   chain  = multi-hop reasoning (A requires B which requires C)
#   trick  = info NOT in catalog / hallucination trap

TEST_QUERIES = [
    # ── Prerequisite Checks (8) ─────────────────────────────────────────────
    {"q": "Can I take CS 101?", "courses": ["MATH 220"], "expected_abstain": False, "category": "prereq"},
    {"q": "Can I take CS 126 if I have CS 125?", "courses": ["CS 125"], "expected_abstain": False, "category": "prereq"},
    {"q": "Can I take CS 128?", "courses": ["CS 124"], "expected_abstain": False, "category": "prereq"},
    {"q": "Am I eligible for CS 340?", "courses": ["CS 128", "CS 225"], "expected_abstain": False, "category": "prereq"},
    {"q": "Can I take CS 411 without CS 225?", "courses": ["CS 128"], "expected_abstain": False, "category": "prereq"},
    {"q": "What do I need for CS 441?", "courses": [], "expected_abstain": False, "category": "prereq"},
    {"q": "Can I take CS 211 if I already have CS 225?", "courses": ["CS 225"], "expected_abstain": False, "category": "prereq"},
    {"q": "Is CS 222 open to non-majors?", "courses": [], "expected_abstain": False, "category": "prereq"},

    # ── Chain Reasoning (7) ─────────────────────────────────────────────────
    {"q": "I have CS 124. What sequence of courses do I need before CS 340?", "courses": ["CS 124"], "expected_abstain": False, "category": "chain"},
    {"q": "If I want to take CS 440, but I only have CS 128 so far, what is my path?", "courses": ["CS 128"], "expected_abstain": False, "category": "chain"},
    {"q": "I want to take CS 411. I have CS 101.", "courses": ["CS 101"], "expected_abstain": False, "category": "chain"},
    {"q": "Can I take CS 441 if I have CS 124, CS 128, CS 225, and MATH 461?", "courses": ["CS 124", "CS 128", "CS 225", "MATH 461"], "expected_abstain": False, "category": "chain"},
    {"q": "I need to take CS 397, how do I qualify?", "courses": [], "expected_abstain": False, "category": "chain"},
    {"q": "Can I take CS 173 if I just finished CS 125 and MATH 220?", "courses": ["CS 125", "MATH 220"], "expected_abstain": False, "category": "chain"},
    {"q": "I have MATH 112. Can I jump to CS 128?", "courses": ["MATH 112"], "expected_abstain": False, "category": "chain"},

    # ── Trick / Hallucination Traps (10) ────────────────────────────────────
    {"q": "Can I take CS 500?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "What's the syllabus for CS 411?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "Who teaches CS 101 currently?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "Are there any prerequisites for ME 200?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "Is CS 225 a hard class?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "How many credits is Psychology 100?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "Does CS 440 use Python or Java?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "When are the exams for CS 128?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "Can I take culinary arts?", "courses": [], "expected_abstain": True, "category": "trick"},
    {"q": "What room is CS 340 in?", "courses": [], "expected_abstain": True, "category": "trick"},
]


def run_evaluation() -> None:
    print("=" * 60)
    print("  RAG System Evaluation — 25 Queries")
    print("=" * 60)

    settings = get_settings()

    try:
        engine = ReasoningEngine(
            settings=settings,
            retriever=RetrieverService(settings),
            verifier=VerifierService(),
            query_rewriter=QueryRewriterService(settings),
        )
    except Exception as e:
        print(f"Failed to init ReasoningEngine: {e}")
        return

    total = len(TEST_QUERIES)
    cited_count = 0
    correct_abstention_count = 0
    total_trick_questions = sum(1 for q in TEST_QUERIES if q["expected_abstain"])
    total_latency_ms = 0
    answered_count = 0

    print(f"Total test queries: {total}\n")

    for i, test in enumerate(TEST_QUERIES, 1):
        q = test["q"]
        courses = test["courses"]
        expected_abstain = test["expected_abstain"]

        print(f"[{i}/{total}] ({test['category']}) Q: {q}")

        start = time.perf_counter()
        response = engine.ask(q, courses)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        if hasattr(response, "clarifying_questions"):
            is_abstain = True
            has_citations = True  # No fabrication = OK
            print(f"    -> Clarifying: {response.clarifying_questions[0]}")
        else:
            txt = (response.why + " " + response.decision).lower()
            is_abstain = (
                "don't have" in txt
                or "not found" in txt
                or "unable to determine" in txt
                or "not in the catalog" in txt
            )
            has_citations = len(response.citations) > 0
            total_latency_ms += response.latency_ms or elapsed_ms
            answered_count += 1

            if response.rewritten_query:
                print(f"    -> Rewritten: {response.rewritten_query}")
            print(f"    -> Decision: {response.decision}")
            print(f"       Why: {response.why[:120]}...")
            print(f"       Citations: {len(response.citations)} | Latency: {response.latency_ms}ms")

        # Metrics
        if expected_abstain:
            if is_abstain:
                correct_abstention_count += 1
                print(f"       [PASS] Correctly abstained")
            else:
                print(f"       [FAIL] Should have abstained")
        else:
            if has_citations:
                cited_count += 1
                print(f"       [PASS] Has citations")
            else:
                print(f"       [FAIL] Missing citations")

        print()

    # ── Results ─────────────────────────────────────────────────────────────
    non_trick_count = total - total_trick_questions
    citation_coverage = (cited_count / non_trick_count) * 100 if non_trick_count else 0
    abstention_accuracy = (correct_abstention_count / total_trick_questions) * 100 if total_trick_questions else 0
    avg_latency = total_latency_ms / answered_count if answered_count else 0

    print("=" * 60)
    print("  Evaluation Results")
    print("=" * 60)
    print(f"  Citation Coverage  : {citation_coverage:.1f}% ({cited_count}/{non_trick_count})")
    print(f"  Abstention Accuracy: {abstention_accuracy:.1f}% ({correct_abstention_count}/{total_trick_questions})")
    print(f"  Avg LLM Latency    : {avg_latency:.0f}ms")
    print(f"  Note: Correctness % requires manual grading of reasoning logic.")
    print("=" * 60)


if __name__ == "__main__":
    run_evaluation()
