"""
apps/descriptive_grading/pipeline/rag.py

Phase 2, Step 4: RAG retrieval. Embeds the **question text** (not the
student answer), queries ChromaDB for the top-k most similar teacher-material
chunks (restricted to the exam's subject), and decides whether there's
enough relevant reference material to ground the LLM's grading.

Using the question text ensures that the reference material is always
topic-relevant regardless of the student's answer quality.
"""
import re

from django.conf import settings

from .embeddings import embed_text
from .vector_store import query_similar_chunks

_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must", "ought",
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "about",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "it", "its", "i", "me", "my", "we", "our", "you", "your", "he",
    "him", "his", "she", "her", "they", "them", "their", "also",
    "often", "however", "usually", "really", "already",
    "since", "back", "now", "well", "even", "new", "want", "like",
    "much", "one", "two", "first", "up", "give", "make", "any",
})


def _get_content_words(text: str) -> set:
    """Extract lowercase content words from text, excluding stop words."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOP_WORDS and len(w) > 1}


def _deduplicate_chunks(chunks):
    """
    Remove near-duplicate chunks that appear because of text-splitter
    overlap.  Keeps the first (highest-similarity) occurrence.
    """
    if not chunks:
        return []

    deduped = []
    seen_tokens = []  # list of token-sets already kept

    for chunk in chunks:
        text = chunk["text"]
        tokens = set(text.lower().split())
        if not tokens:
            continue

        is_dup = False
        for existing in seen_tokens:
            # Jaccard-like: if >85% of tokens overlap, treat as duplicate
            intersection = len(tokens & existing)
            union = len(tokens | existing)
            if union > 0 and intersection / union > 0.85:
                is_dup = True
                break

        if not is_dup:
            deduped.append(chunk)
            seen_tokens.append(tokens)

    return deduped


def compute_answer_relevance(question_text: str, answer_text: str) -> float:
    """
    Hybrid relevance score between the question and the student's answer.

    Uses three complementary signals:
      1. Embedding cosine similarity — catches deep semantic relevance
         (e.g. answer uses different words but describes the same concept).
      2. Keyword overlap — catches surface-level relevance when the answer
         shares content words with the question even if embeddings are weak
         (short answers, different sentence structures, etc.).
      3. Question containment — detects when the answer contains most of the
         question text (e.g. student copied the question). This prevents
         false positives from OCR errors on identical text.

    Returns the *maximum* of the three signals so that a relevant answer
    passes as long as it is strong on at least one axis.  Truly off-topic
    answers score low on all and get flagged.
    """
    # --- Signal 1: embedding cosine similarity ---
    question_vector = embed_text(question_text)
    answer_vector = embed_text(answer_text)
    embedding_sim = float(sum(a * b for a, b in zip(question_vector, answer_vector)))

    # --- Signal 2: keyword overlap ---
    q_words = _get_content_words(question_text)
    a_words = _get_content_words(answer_text)
    q_overlap = 0.0

    if q_words:
        # Fraction of question content words that appear in the answer
        q_overlap = len(q_words & a_words) / len(q_words)
        # Jaccard index (symmetric)
        union = q_words | a_words
        jaccard = len(q_words & a_words) / len(union) if union else 0.0
        keyword_sim = max(q_overlap, jaccard)
    else:
        keyword_sim = 0.0

    # --- Signal 3: question containment ---
    # If the answer contains most of the question's content words,
    # it's definitely on-topic (student may have copied the question).
    containment_sim = q_overlap

    return max(embedding_sim, keyword_sim, containment_sim)


def retrieve_context(question_text: str, subject: str) -> dict:
    """
    Retrieve the most relevant reference-material chunks for a given
    question by computing cosine similarity between the question text
    and the stored teacher-material chunks in ChromaDB.

    Args:
        question_text: The exam question text (used as the query).
        subject:       The exam subject (used to filter chunks).

    Returns:
        {
            "context_available": bool,
            "similarity_score": float,                     # best cosine similarity
            "retrieved_chunks": list[dict],                 # [{"text": str, "similarity_score": float}, ...]
            "combined_context": str,                        # joined chunk texts for prompt
        }
    """
    query_vector = embed_text(question_text)

    # Over-fetch to ensure we have enough after deduplication
    fetch_n = settings.TOP_K_CHUNKS * 3
    result = query_similar_chunks(
        query_vector=query_vector,
        subject=subject,
        n_results=fetch_n,
    )

    documents = result["documents"]
    similarities = result["similarities"]
    metadatas = result.get("metadatas", [])

    chunks_with_scores = [
        {
            "text": doc,
            "similarity_score": round(sim, 4),
            "chunk_index": meta.get("chunk_index", i) if meta else i,
            "overlap_pct": meta.get("overlap_pct", 0.0) if meta else 0.0,
        }
        for i, (doc, sim, meta) in enumerate(zip(documents, similarities, metadatas))
    ]

    chunks_with_scores = _deduplicate_chunks(chunks_with_scores)
    chunks_with_scores = chunks_with_scores[:settings.TOP_K_CHUNKS]

    best_similarity = max(similarities) if similarities else 0.0
    context_available = best_similarity >= settings.SIMILARITY_THRESHOLD

    return {
        "context_available": context_available,
        "similarity_score": best_similarity,
        "retrieved_chunks": chunks_with_scores,
        "combined_context": "\n\n".join(c["text"] for c in chunks_with_scores) if context_available else "",
    }


def get_question_relevant_chunks(question_text: str, subject: str) -> dict:
    """
    On-demand retrieval for the teacher preview endpoint.
    Returns the relevant chunks for a question without going through
    the full grading pipeline.

    Returns:
        {
            "similarity_score": float,
            "chunks": list[dict],  # [{"text": str, "similarity_score": float, "chunk_index": int, "overlap_pct": float}, ...]
        }
    """
    query_vector = embed_text(question_text)

    fetch_n = settings.TOP_K_CHUNKS * 3
    result = query_similar_chunks(
        query_vector=query_vector,
        subject=subject,
        n_results=fetch_n,
    )

    documents = result["documents"]
    similarities = result["similarities"]
    metadatas = result.get("metadatas", [])

    chunks_with_scores = [
        {
            "text": doc,
            "similarity_score": round(sim, 4),
            "chunk_index": meta.get("chunk_index", i) if meta else i,
            "overlap_pct": meta.get("overlap_pct", 0.0) if meta else 0.0,
        }
        for i, (doc, sim, meta) in enumerate(zip(documents, similarities, metadatas))
    ]

    chunks_with_scores = _deduplicate_chunks(chunks_with_scores)
    chunks_with_scores = chunks_with_scores[:settings.TOP_K_CHUNKS]

    best_similarity = max(similarities) if similarities else 0.0

    return {
        "similarity_score": best_similarity,
        "chunks": chunks_with_scores,
    }
