"""
apps/descriptive_grading/pipeline/rag.py

Phase 2, Step 4: RAG retrieval. Embeds the student's cleaned OCR text,
queries ChromaDB for the top-k most similar teacher-material chunks
(restricted to the exam's subject), and decides whether there's enough
relevant reference material to ground the LLM's grading.
"""
from django.conf import settings

from .embeddings import embed_text
from .vector_store import query_similar_chunks


def retrieve_context(cleaned_answer_text: str, subject: str) -> dict:
    """
    Run the retrieval step for a single student answer.

    Returns:
        {
            "context_available": bool,
            "similarity_score": float,      # best (highest) similarity among top-k
            "retrieved_chunks": list[str],  # chunk texts, empty if context_available=False
            "combined_context": str,        # joined chunk texts for prompt building
        }
    """
    query_vector = embed_text(cleaned_answer_text)

    result = query_similar_chunks(
        query_vector=query_vector,
        subject=subject,
        n_results=settings.TOP_K_CHUNKS,
    )

    documents = result["documents"]
    similarities = result["similarities"]

    best_similarity = max(similarities) if similarities else 0.0
    context_available = best_similarity >= settings.SIMILARITY_THRESHOLD

    return {
        "context_available": context_available,
        "similarity_score": best_similarity,
        "retrieved_chunks": documents if context_available else [],
        "combined_context": "\n\n".join(documents) if context_available else "",
    }
