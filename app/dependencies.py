"""
Dependency injection module — centralizes all service wiring.
Pattern adopted from eve-core: clean DI functions consumed via Depends().
"""

from functools import lru_cache

from .core.config import Settings, get_settings
from .services.retriever import RetrieverService
from .services.query_rewriter import QueryRewriterService
from .services.verifier import VerifierService
from .services.reasoning import ReasoningEngine


# ── Singletons (created once, reused across requests) ──────────────────────────

_settings: Settings | None = None
_retriever: RetrieverService | None = None
_verifier: VerifierService | None = None
_query_rewriter: QueryRewriterService | None = None


def get_settings_dep() -> Settings:
    """Return the cached application settings."""
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def get_retriever_dep() -> RetrieverService:
    """Return the singleton RetrieverService."""
    global _retriever
    if _retriever is None:
        _retriever = RetrieverService(get_settings_dep())
    return _retriever


def get_verifier_dep() -> VerifierService:
    """Return the singleton VerifierService."""
    global _verifier
    if _verifier is None:
        _verifier = VerifierService()
    return _verifier


def get_query_rewriter_dep() -> QueryRewriterService:
    """Return the singleton QueryRewriterService."""
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = QueryRewriterService(get_settings_dep())
    return _query_rewriter


def get_reasoning_engine_dep() -> ReasoningEngine:
    """
    Build ReasoningEngine with all its dependencies.
    This is request-scoped (lightweight — all heavy objects are singletons).
    """
    return ReasoningEngine(
        settings=get_settings_dep(),
        retriever=get_retriever_dep(),
        verifier=get_verifier_dep(),
        query_rewriter=get_query_rewriter_dep(),
    )
