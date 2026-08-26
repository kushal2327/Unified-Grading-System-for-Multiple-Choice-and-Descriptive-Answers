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


def _compute_overlap_pcts(chunks: list, overlap_chars: int) -> list:
    """Compute the actual overlap percentage for each chunk relative to its
    predecessor.  Returns a list of floats (0-100).  The first chunk is 0%.

    When the overlap between two consecutive chunks comes from a paragraph
    boundary (double newline), the overlap is reported as 0 % because the
    chunks are semantically distinct.
    """
    if len(chunks) <= 1:
        return [0.0]

    pcts = [0.0]
    for i in range(1, len(chunks)):
        prev = chunks[i - 1]
        cur = chunks[i]

        # Find the longest suffix of prev that matches a prefix of cur.
        max_possible = min(len(prev), len(cur), overlap_chars)
        overlap_len = 0
        for length in range(max_possible, 0, -1):
            if prev.endswith(cur[:length]):
                overlap_len = length
                break

        # If the overlap crosses a paragraph boundary, treat as 0 %
        if overlap_len > 0:
            # Check if a double-newline exists in the overlapping region
            overlap_region = prev[-overlap_len:]
            if "\n\n" in overlap_region:
                overlap_len = 0

        chunk_len = len(cur)
        pct = round((overlap_len / chunk_len) * 100, 1) if chunk_len > 0 else 0.0
        pcts.append(pct)

    return pcts


def split_into_chunks(raw_text: str) -> tuple:
    """Split raw text into overlapping chunks using LangChain.

    Returns (chunks, overlap_pcts) where overlap_pcts is a list of
    per-chunk overlap percentages (0 = first chunk or paragraph break).
    """
    overlap_pct = getattr(settings, "CHUNK_OVERLAP_PCT", 20)
    overlap_pct = max(0, min(20, overlap_pct))  # clamp to 0-20
    overlap_chars = int(settings.CHUNK_SIZE * overlap_pct / 100)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=overlap_chars,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = splitter.split_text(raw_text)
    overlap_pcts = _compute_overlap_pcts(chunks, overlap_chars)
    return chunks, overlap_pcts


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

    chunks, overlap_pcts = split_into_chunks(raw_text)
    if not chunks:
        raise ValueError("Text splitter produced zero chunks.")

    vectors = embed_texts(chunks)

    chunk_ids = store_chunks(
        chunks=chunks,
        embeddings=vectors,
        subject=material.subject,
        teacher_id=material.teacher_id,
        material_id=material.id,
        overlap_pcts=overlap_pcts,
    )

    material.chunked = True
    material.save(update_fields=["chunked"])

    return {
        "material_id": material.id,
        "num_chunks": len(chunks),
        "chunk_ids": chunk_ids,
    }
