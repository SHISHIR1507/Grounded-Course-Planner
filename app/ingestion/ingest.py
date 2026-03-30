"""
Ingestion pipeline: loads courses.json → LangChain Documents → FAISS vectorstore.

This module is ONLY used offline for building the vectorstore.
It is NOT imported at runtime by the API.

Adopts eve-core chunker patterns:
- Token-based chunking via tiktoken (not raw character count)
- RecursiveCharacterTextSplitter.from_tiktoken_encoder
"""

import json
import sys
from pathlib import Path

import tiktoken
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

# Add project root to path so we can import app.core
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import get_settings


def load_courses(json_path: str) -> list[dict]:
    """Load raw course data from JSON file."""
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Course data not found at: {path.resolve()}")

    with open(path, encoding="utf-8") as f:
        courses = json.load(f)

    print(f"  Loaded {len(courses)} courses from {path}")
    return courses


def courses_to_documents(courses: list[dict]) -> list[Document]:
    """
    Convert raw course dicts into LangChain Document objects
    with structured metadata for citation tracking.
    """
    documents: list[Document] = []

    for course in courses:
        content_parts = [
            f"Course: {course['course']}",
            f"Title: {course.get('title', 'N/A')}",
            f"Description: {course.get('content', 'N/A')}",
            f"Prerequisites: {course.get('prerequisite', 'Not specified')}",
        ]
        page_content = "\n".join(content_parts)

        metadata = {
            "course": course["course"],
            "title": course.get("title", ""),
            "source": course.get("source", "Unknown"),
            "section": course.get("section", course["course"]),
            "prerequisite": course.get("prerequisite", "Not specified"),
        }

        documents.append(Document(page_content=page_content, metadata=metadata))

    print(f"  Created {len(documents)} LangChain Documents")
    return documents


def _get_token_encoder(model_name: str = "gpt-4o") -> tiktoken.Encoding:
    """Get tiktoken encoder for token-based chunking (eve-core pattern)."""
    try:
        return tiktoken.encoding_for_model(model_name)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")


def chunk_documents(
    documents: list[Document],
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    """
    Split documents into smaller chunks for better retrieval.
    Uses token-based chunking via tiktoken (adopted from eve-core's chunker.py).
    """
    # Convert character-based config into token-based limits
    chunk_tokens = max(100, chunk_size // 4)
    overlap_tokens = max(20, chunk_overlap // 4)

    encoder = _get_token_encoder()

    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=encoder.name,
        chunk_size=chunk_tokens,
        chunk_overlap=overlap_tokens,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_documents(documents)
    print(
        f"  Split into {len(chunks)} chunks "
        f"(token_size={chunk_tokens}, token_overlap={overlap_tokens})"
    )
    return chunks


def build_vectorstore(chunks: list[Document], settings) -> FAISS:
    """Create a FAISS vectorstore from document chunks using OpenAI embeddings."""
    embeddings = OpenAIEmbeddings(
        model=settings.embedding_model,
        openai_api_key=settings.openai_api_key,
    )

    vectorstore = FAISS.from_documents(chunks, embeddings)
    print(f"  Built FAISS vectorstore with {len(chunks)} vectors")
    return vectorstore


def save_vectorstore(vectorstore: FAISS, path: str) -> None:
    """Persist FAISS vectorstore to disk."""
    Path(path).mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(path)
    print(f"  Saved vectorstore to {path}/")


def run_ingestion() -> None:
    """Execute the full ingestion pipeline."""
    settings = get_settings()

    print("=" * 60)
    print("  Course Catalog Ingestion Pipeline")
    print("=" * 60)

    # Step 1: Load raw data
    courses = load_courses(settings.courses_json_path)

    # Step 2: Convert to LangChain Documents
    documents = courses_to_documents(courses)

    # Step 3: Token-based chunking (eve-core pattern)
    chunks = chunk_documents(
        documents,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    # Step 4: Build FAISS vectorstore
    vectorstore = build_vectorstore(chunks, settings)

    # Step 5: Save to disk
    save_vectorstore(vectorstore, settings.vectorstore_path)

    print("=" * 60)
    print(" Ingestion complete!")
    print("=" * 60)


if __name__ == "__main__":
    run_ingestion()
