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
        {
            "chunk_index": meta.get("chunk_index", i),
            "text": doc,
            "overlap_pct": meta.get("overlap_pct", 0.0),
        }
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
    overlap_pcts: Optional[List[float]] = None,
) -> List[str]:
    """
    Store a batch of chunk texts + their vectors in ChromaDB with metadata:
    {subject, teacher_id, chapter, chunk_index, material_id, overlap_pct}

    Returns the list of generated chunk ids.
    """
    collection = get_collection()
    ids = [f"mat{material_id}-chunk{i}-{uuid.uuid4().hex[:8]}" for i in range(len(chunks))]
    if overlap_pcts is None:
        overlap_pcts = [0.0] * len(chunks)
    metadatas = [
        {
            "subject": subject,
            "teacher_id": str(teacher_id),
            "chapter": chapter or "",
            "chunk_index": i,
            "material_id": material_id,
            "overlap_pct": overlap_pcts[i],
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
    restricted to the given subject (case-insensitive).

    Returns a dict: {"documents": [...], "similarities": [...], "ids": [...]}
    where similarities are cosine similarity scores (1 = identical, 0 = opposite).
    """
    collection = get_collection()

    if collection.count() == 0:
        return {"documents": [], "similarities": [], "ids": []}

    # Query without subject filter (ChromaDB subject filter is case-sensitive
    # and brittle).  We over-fetch, then filter by subject in Python.
    fetch_n = max(n_results * 5, 20)
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=fetch_n,
    )

    all_documents = results.get("documents", [[]])[0]
    all_distances = results.get("distances", [[]])[0]
    all_ids = results.get("ids", [[]])[0]
    all_metadatas = results.get("metadatas", [[]])[0]

    # Filter to only chunks whose subject matches (case-insensitive)
    subject_lower = subject.strip().lower()
    documents, similarities, ids, metadatas = [], [], [], []
    for doc, dist, cid, meta in zip(all_documents, all_distances, all_ids, all_metadatas):
        chunk_subject = (meta.get("subject") or "").strip().lower()
        if chunk_subject == subject_lower:
            documents.append(doc)
            similarities.append(1 - dist)
            ids.append(cid)
            metadatas.append(meta)

    # If no subject match found, return top results anyway so the teacher
    # can see what was retrieved (better than showing nothing).
    if not documents:
        for doc, dist, cid, meta in zip(all_documents[:n_results], all_distances[:n_results], all_ids[:n_results], all_metadatas[:n_results]):
            documents.append(doc)
            similarities.append(1 - dist)
            ids.append(cid)
            metadatas.append(meta)

    return {"documents": documents, "similarities": similarities, "ids": ids, "metadatas": metadatas}
