"""
Retriever service: loads the FAISS vectorstore and provides
similarity search with metadata for citations.

Adopts eve-core patterns: explicit settings injection, scored retrieval,
structured SourceChunk output.
"""

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from app.core.config import Settings


class RetrieverService:
    """Manages FAISS vectorstore loading and document retrieval."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._vectorstore: FAISS | None = None

    def _load_vectorstore(self) -> FAISS:
        """Load persisted FAISS vectorstore from disk."""
        vs_path = Path(self._settings.vectorstore_path)
        if not vs_path.exists():
            raise FileNotFoundError(
                f"Vectorstore not found at '{vs_path.resolve()}'. "
                "Run the ingestion pipeline first: python -m app.ingestion.ingest"
            )

        embeddings = OpenAIEmbeddings(
            model=self._settings.embedding_model,
            openai_api_key=self._settings.openai_api_key,
        )

        return FAISS.load_local(
            str(vs_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )

    @property
    def vectorstore(self) -> FAISS:
        """Lazy-load the vectorstore on first access."""
        if self._vectorstore is None:
            self._vectorstore = self._load_vectorstore()
        return self._vectorstore

    def retrieve(self, query: str, k: int | None = None) -> list[Document]:
        """
        Perform similarity search against the vectorstore.

        Args:
            query: The search query string.
            k: Number of results to return (defaults to RETRIEVER_K from config).

        Returns:
            List of Document objects with page_content and metadata.
        """
        k = k or self._settings.retriever_k
        return self.vectorstore.similarity_search(query, k=k)

    def retrieve_with_scores(
        self, query: str, k: int | None = None
    ) -> list[tuple[Document, float]]:
        """
        Perform similarity search and return results with relevance scores.
        Pattern from eve-core: always expose scores for transparency.

        Args:
            query: The search query string.
            k: Number of results to return.

        Returns:
            List of (Document, score) tuples sorted by relevance.
        """
        k = k or self._settings.retriever_k
        return self.vectorstore.similarity_search_with_score(query, k=k)

    def format_context(self, documents: list[Document]) -> str:
        """
        Format retrieved documents into a context string for the LLM prompt.
        Includes metadata for citation tracking.

        Mirrors eve-core's context_blocks pattern:
        "Document: <title>\nChunk: <content>"
        """
        context_parts: list[str] = []

        for i, doc in enumerate(documents, 1):
            meta = doc.metadata
            header = (
                f"[Source {i}] "
                f"Course: {meta.get('course', 'N/A')} | "
                f"Section: {meta.get('section', 'N/A')} | "
                f"Source: {meta.get('source', 'N/A')} | "
                f"Prerequisite: {meta.get('prerequisite', 'N/A')}"
            )
            context_parts.append(f"{header}\n{doc.page_content}")

        return "\n\n---\n\n".join(context_parts)

    def extract_citations(self, documents: list[Document]) -> list[str]:
        """
        Extract deduplicated citation strings from document metadata.
        """
        citations: list[str] = []
        seen: set[str] = set()

        for doc in documents:
            meta = doc.metadata
            course_code = meta.get('course', 'Unknown')
            citation = f"- {course_code} (Prerequisite section)"
            
            if citation not in seen:
                seen.add(citation)
                citations.append(citation)

        return citations
