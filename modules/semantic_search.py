"""Semantic search using FAISS embeddings."""

from modules.faiss_builder import faiss_search, get_candidate_chunks


def semantic_search(query: str, top_k: int = 50) -> list[dict]:
    """Search FAISS index with query, return deduplicated candidate-level results."""
    chunks = faiss_search(query, top_k=top_k * 4)

    # Aggregate scores per candidate (max similarity across all their chunks)
    candidate_scores: dict[str, float] = {}
    candidate_evidence: dict[str, list[str]] = {}

    for chunk in chunks:
        cid = chunk["candidate_id"]
        score = chunk["similarity_score"]
        if cid not in candidate_scores or score > candidate_scores[cid]:
            candidate_scores[cid] = score
        if cid not in candidate_evidence:
            candidate_evidence[cid] = []
        candidate_evidence[cid].append(chunk["text"][:200])

    ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    return [
        {
            "candidate_id": cid,
            "semantic_score": round(score * 100, 2),
            "evidence_snippets": candidate_evidence[cid][:3],
        }
        for cid, score in ranked
    ]


def get_rag_context(candidate_id: str, query: str, top_n: int = 5) -> list[str]:
    """Retrieve the most relevant text chunks for a candidate given a query."""
    from modules.faiss_builder import faiss_search
    chunks = faiss_search(query, top_k=200)
    candidate_chunks = [c for c in chunks if c["candidate_id"] == candidate_id]
    candidate_chunks.sort(key=lambda x: x["similarity_score"], reverse=True)
    return [c["text"] for c in candidate_chunks[:top_n]]
