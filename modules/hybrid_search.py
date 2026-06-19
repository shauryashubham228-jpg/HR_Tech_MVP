"""Hybrid search: Structured (SQL) → Semantic (FAISS) → Merge & Score → Rank."""

import uuid
from modules.structured_search import get_candidates_for_jd
from modules.semantic_search import semantic_search
from modules.scoring import (
    compute_match_score,
    compute_confidence_score,
    compute_engagement_score,
    compute_final_score,
)
from modules.database import (
    get_candidates_by_ids,
    save_job,
    upsert_job_candidate,
)


def run_hybrid_search(structured_jd: dict, top_k: int = 20) -> tuple[str, list[dict]]:
    """
    Full hybrid search pipeline.

    Returns
    -------
    job_id : str
        Newly created job ID saved in SQLite.
    ranked_candidates : list[dict]
        Top-K candidates with all scores attached.
    """
    job_id = structured_jd.get("job_id", str(uuid.uuid4())[:8])

    # ── Step 1: Structured search ────────────────────────────────────────────
    print("🔍 Step 1: Structured search...")
    structured_candidates = get_candidates_for_jd(structured_jd)
    structured_ids = {c["candidate_id"] for c in structured_candidates}
    print(f"   Found {len(structured_ids)} candidates via SQL")

    if not structured_ids:
        print("   No SQL matches — returning empty.")
        return job_id, []

    # ── Step 2: Semantic re-rank WITHIN the SQL pool only ───────────────────
    # FAISS never adds new candidates — it only gives semantic scores to
    # candidates who already passed the SQL hard filter.
    print("🔍 Step 2: Semantic re-rank within SQL pool...")
    query_text = _build_semantic_query(structured_jd)
    semantic_results = semantic_search(query_text, top_k=500)
    semantic_map = {
        r["candidate_id"]: r
        for r in semantic_results
        if r["candidate_id"] in structured_ids   # intersect with SQL pool
    }
    print(f"   {len(semantic_map)} of {len(structured_ids)} SQL candidates matched semantically")

    # Use SQL candidates as the only pool
    candidates_by_id = {c["candidate_id"]: c for c in structured_candidates}

    # ── Step 4: Score & rank ─────────────────────────────────────────────────
    print("📊 Step 3: Scoring candidates...")
    ranked = []
    for cid, candidate in candidates_by_id.items():
        sem_score = semantic_map.get(cid, {}).get("semantic_score", 0.0)
        match = compute_match_score(candidate, structured_jd, sem_score)
        confidence = compute_confidence_score(candidate)
        engagement = compute_engagement_score(cid)
        final = compute_final_score(
            match["match_score"],
            confidence["confidence_score"],
            engagement["engagement_score"],
        )
        enriched = {
            **candidate,
            **match,
            "confidence_score": confidence["confidence_score"],
            "confidence_evidence": confidence["evidence"],
            "engagement_score": engagement["engagement_score"],
            "engagement_breakdown": engagement["breakdown"],
            "final_score": final,
            "updated_score": final,
            "semantic_evidence": semantic_map.get(cid, {}).get("evidence_snippets", []),
        }
        ranked.append(enriched)

    ranked.sort(key=lambda x: x["final_score"], reverse=True)
    top_candidates = ranked[:top_k]

    # ── Step 5: Persist job + scores ─────────────────────────────────────────
    save_job(job_id, structured_jd.get("_raw_jd", ""), structured_jd)
    for c in top_candidates:
        upsert_job_candidate(job_id, c["candidate_id"], {
            "match_score": c["match_score"],
            "confidence_score": c["confidence_score"],
            "engagement_score": c["engagement_score"],
            "final_score": c["final_score"],
        })

    print(f"✅ Hybrid search complete. Top {len(top_candidates)} candidates ranked.")
    return job_id, top_candidates


def _build_semantic_query(jd: dict) -> str:
    parts = []
    if jd.get("role"):
        parts.append(jd["role"])
    if jd.get("skills"):
        parts.append(", ".join(jd["skills"][:6]))
    if jd.get("responsibilities"):
        parts.append(". ".join(jd["responsibilities"][:3]))
    if jd.get("industry"):
        parts.append(jd["industry"])
    return " ".join(parts)
