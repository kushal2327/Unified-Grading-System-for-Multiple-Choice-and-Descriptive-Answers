"""
apps/descriptive_grading/pipeline/vector_store.py

Thin wrapper around a persistent ChromaDB collection that stores teacher
reference-material chunks (with their embeddings) and lets the RAG step
query the top-k most similar chunks for a given subject.

All teacher chunks live in a single collection ("teacher_materials");
subject / teacher_id / chapter / chunk_index are stored as metadata so
we can filter with `where={"subject": ...}` at query time, exactly as
specified in the pipeline design.
"""
import uuid
from typing import Dict, List, Optional

import chromadb
from django.conf import settings

COLLECTION_NAME = "teacher_materials"

_client = None


def get_client() -> chromadb.Client:
    """Lazily create (and cache) the persistent ChromaDB client."""
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMADB_PERSIST_PATH)
    return _client


def get_collection():
    client = get_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
def get_chunks_for_material(material_id: int) -> list:
    """
    Retrieve every stored chunk for a given teacher material, ordered
    by chunk_index, for display in the "view extracted chunks" UI.
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    result = collection.get(where={"material_id": material_id})
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])

    chunks = [
        {"chunk_index": meta.get("chunk_index", i), "text": doc}
        for i, (doc, meta) in enumerate(zip(documents, metadatas))
    ]
    chunks.sort(key=lambda c: c["chunk_index"])
    return chunks

def store_chunks(
    chunks: List[str],
    embeddings: List[List[float]],
    subject: str,
    teacher_id: int,
    material_id: int,
    chapter: Optional[str] = "",
) -> List[str]:
    """
    Store a batch of chunk texts + their vectors in ChromaDB with metadata:
    {subject, teacher_id, chapter, chunk_index, material_id}

    Returns the list of generated chunk ids.
    """
    collection = get_collection()
    ids = [f"mat{material_id}-chunk{i}-{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
    metadatas = [
        {
            "subject": subject,
            "teacher_id": str(teacher_id),
            "chapter": chapter or "",
            "chunk_index": i,
            "material_id": material_id,
        }
        for i in range(len(chunks))
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )
    return ids


def query_similar_chunks(
    query_vector: List[float],
    subject: str,
    n_results: int = 3,
) -> Dict:
    """
    Query ChromaDB for the top-k chunks most similar to query_vector,
    restricted to the given subject.

    Returns a dict: {"documents": [...], "distances": [...], "ids": [...]}
    where distances are cosine distances (0 = identical, 2 = opposite).
    We convert to a similarity score (1 - distance) before returning
    so callers can compare directly against SIMILARITY_THRESHOLD.
    """
    collection = get_collection()

    if collection.count() == 0:
        return {"documents": [], "similarities": [], "ids": []}

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results,
        where={"subject": subject},
    )

    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]
    ids = results.get("ids", [[]])[0]

    # ChromaDB's cosine "distance" is 1 - cosine_similarity, so
    # similarity = 1 - distance.
    similarities = [1 - d for d in distances]

    return {"documents": documents, "similarities": similarities, "ids": ids}
