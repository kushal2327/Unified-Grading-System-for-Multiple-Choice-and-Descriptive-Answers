"""
apps/descriptive_grading/pipeline/material_ingestion.py

Phase 1 of the pipeline (runs once per teacher upload):
  1. Extract raw text from the uploaded file (PDF via PyMuPDF, or .txt directly)
  2. Split it into overlapping chunks with LangChain's
     RecursiveCharacterTextSplitter
  3. Embed each chunk (all-MiniLM-L6-v2) and store it in ChromaDB
  4. Mark teacher_materials.chunked = True
"""
import os

import fitz  # PyMuPDF
from django.conf import settings
try:
    # Modern langchain (>=0.1) ships the splitter in its own package.
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - fallback for older langchain versions
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from .embeddings import embed_texts
from .vector_store import store_chunks


def extract_text(file_path: str) -> str:
    """Extract raw text from a PDF or plain-text file."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text_parts.append(page.get_text())
        return "\n".join(text_parts)

    # plain text (.txt, .md, etc.)
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def split_into_chunks(raw_text: str) -> list:
    """Split raw text into overlapping chunks using LangChain."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )
    return splitter.split_text(raw_text)


def process_teacher_material(material) -> dict:
    """
    Full ingestion pipeline for a single TeacherMaterial instance:
    extract -> chunk -> embed -> store in ChromaDB -> mark chunked=True.

    Returns a small summary dict for the API response.
    """
    file_path = material.file_path.path
    raw_text = extract_text(file_path)

    if not raw_text or not raw_text.strip():
        raise ValueError("No extractable text found in the uploaded file.")

    chunks = split_into_chunks(raw_text)
    if not chunks:
        raise ValueError("Text splitter produced zero chunks.")

    vectors = embed_texts(chunks)

    chunk_ids = store_chunks(
        chunks=chunks,
        embeddings=vectors,
        subject=material.subject,
        teacher_id=material.teacher_id,
        material_id=material.id,
    )

    material.chunked = True
    material.save(update_fields=["chunked"])

    return {
        "material_id": material.id,
        "num_chunks": len(chunks),
        "chunk_ids": chunk_ids,
    }
