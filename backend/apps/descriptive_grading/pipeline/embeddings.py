"""
apps/descriptive_grading/pipeline/embeddings.py

Wraps sentence-transformers/all-MiniLM-L6-v2 to turn text (a teacher
reference chunk, or a student's cleaned OCR answer) into a 384-dim
L2-normalized vector.

The model is loaded once per process (module-level singleton) since
loading it is the expensive part - encoding individual strings is cheap.
"""
from functools import lru_cache
from typing import List, Union

from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Lazily load and cache the sentence-transformer model."""
    return SentenceTransformer(MODEL_NAME)


def embed_text(text: str) -> List[float]:
    """
    Encode a single string into a 384-dim, L2-normalized vector
    (values range -1.0 to +1.0).
    """
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return vector.tolist()


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch-encode multiple strings at once (used when embedding chunks)."""
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()
