"""Build and manage the FAISS vector index for semantic search."""

import os
import json
import pickle
import numpy as np
from typing import Optional

FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_index")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

_embedder = None
_faiss_index = None
_metadata_store: list[dict] = []


def get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
        print(f"✅ Embedder loaded: {EMBEDDING_MODEL}")
    return _embedder


def _candidate_to_chunks(candidate: dict) -> list[dict]:
    """Convert a candidate record into text chunks with metadata."""
    chunks = []
    cid = candidate["candidate_id"]
    name = candidate.get("name", "")
    role = candidate.get("role", "")

    if candidate.get("about_section"):
        chunks.append({
            "text": f"About {name}: {candidate['about_section']}",
            "candidate_id": cid,
            "chunk_type": "about",
            "chunk_id": f"{cid}_about",
        })

    for proj in candidate.get("projects", []):
        text = (
            f"Project: {proj['title']}. {proj['description']} "
            f"Skills used: {', '.join(proj.get('skills_used', []))}."
        )
        chunks.append({
            "text": text,
            "candidate_id": cid,
            "chunk_type": "project",
            "chunk_id": f"{cid}_{proj.get('project_id', 'p')}",
        })

    for we in candidate.get("work_experience", []):
        resps = " ".join(we.get("responsibilities", []))
        text = (
            f"{name} worked as {we['title']} at {we['company']} for {we['tenure_years']} years. "
            f"{resps}"
        )
        chunks.append({
            "text": text,
            "candidate_id": cid,
            "chunk_type": "experience",
            "chunk_id": f"{cid}_{we['company'][:8]}",
        })

    skills_text = (
        f"{name} has skills in: {', '.join(candidate.get('skills', []))}. "
        f"Industry: {candidate.get('industry', '')}. Role: {role}."
    )
    chunks.append({
        "text": skills_text,
        "candidate_id": cid,
        "chunk_type": "skills",
        "chunk_id": f"{cid}_skills",
    })

    return chunks


def build_faiss_index(candidates: list[dict]):
    """Embed all candidate chunks and persist the FAISS index to disk."""
    import faiss

    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)
    embedder = get_embedder()

    print("🔨 Building FAISS index...")
    all_chunks: list[dict] = []
    for c in candidates:
        all_chunks.extend(_candidate_to_chunks(c))

    texts = [chunk["text"] for chunk in all_chunks]
    print(f"   Embedding {len(texts)} chunks...")
    embeddings = embedder.encode(texts, batch_size=64, show_progress_bar=True,
                                 convert_to_numpy=True, normalize_embeddings=True)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)  # Inner-product ≈ cosine on normalized vecs
    index.add(embeddings.astype(np.float32))

    faiss.write_index(index, os.path.join(FAISS_INDEX_PATH, "index.faiss"))
    with open(os.path.join(FAISS_INDEX_PATH, "metadata.pkl"), "wb") as f:
        pickle.dump(all_chunks, f)

    print(f"✅ FAISS index built: {index.ntotal} vectors (dim={dim})")
    return index, all_chunks


def load_faiss_index():
    """Load FAISS index and metadata from disk."""
    global _faiss_index, _metadata_store
    import faiss

    idx_path = os.path.join(FAISS_INDEX_PATH, "index.faiss")
    meta_path = os.path.join(FAISS_INDEX_PATH, "metadata.pkl")

    if not os.path.exists(idx_path):
        raise FileNotFoundError(
            "FAISS index not found. Run build_faiss_index() first."
        )

    _faiss_index = faiss.read_index(idx_path)
    with open(meta_path, "rb") as f:
        _metadata_store = pickle.load(f)

    print(f"✅ FAISS index loaded: {_faiss_index.ntotal} vectors")
    return _faiss_index, _metadata_store


def faiss_search(query: str, top_k: int = 50, chunk_type: Optional[str] = None) -> list[dict]:
    """Return top-k candidate chunks most semantically similar to the query."""
    global _faiss_index, _metadata_store

    if _faiss_index is None:
        load_faiss_index()

    embedder = get_embedder()
    q_vec = embedder.encode([query], convert_to_numpy=True,
                             normalize_embeddings=True).astype(np.float32)

    scores, indices = _faiss_index.search(q_vec, top_k * 3)

    results = []
    seen_candidates = set()
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(_metadata_store):
            continue
        chunk = _metadata_store[idx]
        if chunk_type and chunk["chunk_type"] != chunk_type:
            continue
        cid = chunk["candidate_id"]
        if cid in seen_candidates:
            results.append({**chunk, "similarity_score": float(score)})
            continue
        seen_candidates.add(cid)
        results.append({**chunk, "similarity_score": float(score)})
        if len([r for r in results if r["candidate_id"] not in
                {r2["candidate_id"] for r2 in results[:-1]}]) >= top_k:
            break

    return results[:top_k]


def get_candidate_chunks(candidate_id: str) -> list[dict]:
    """Retrieve all stored chunks for a specific candidate."""
    global _metadata_store
    if not _metadata_store:
        load_faiss_index()
    return [c for c in _metadata_store if c["candidate_id"] == candidate_id]


def index_exists() -> bool:
    return os.path.exists(os.path.join(FAISS_INDEX_PATH, "index.faiss"))
