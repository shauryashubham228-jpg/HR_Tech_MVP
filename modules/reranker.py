"""Dynamic re-ranking – updates scores for a specific job without touching master profile."""

from modules.database import (
    save_assessment,
    update_assessment_score,
    get_job_candidates,
    get_assessments,
)


def apply_assessment_and_rerank(
    job_id: str,
    candidate_id: str,
    question: str,
    answer: str,
    assessment_result: dict,
    current_final_score: float,
    requirement: str = "",
) -> float:
    """
    Store assessment, compute new updated_score (capped 0-100), and persist.
    Always reads current updated_score from DB so each question chains
    on the previous result, not the original final_score.
    Returns the new updated_score.
    """
    # Always use the latest persisted updated_score, not the caller-supplied value,
    # so sequential assessments accumulate correctly even if caller passes stale data.
    from modules.database import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT updated_score FROM job_candidates WHERE job_id=? AND candidate_id=?",
        (job_id, candidate_id)
    ).fetchone()
    conn.close()
    base = row["updated_score"] if row else current_final_score

    score_impact    = assessment_result.get("score_impact", 0)
    assessment_score = assessment_result.get("assessment_score", 0)

    # Hard cap: score can never exceed 100 or go below 0
    new_score = min(100.0, max(0.0, base + score_impact))

    save_assessment(
        job_id, candidate_id, question, answer,
        assessment_score, score_impact,
        verdict=assessment_result.get("verdict", ""),
        feedback=assessment_result.get("feedback", ""),
        targets_requirement=requirement,
    )
    update_assessment_score(job_id, candidate_id, new_score)

    return round(new_score, 2)


def get_reranked_candidates(job_id: str) -> list[dict]:
    """Return job candidates sorted by updated_score (post-assessment ranking)."""
    candidates = get_job_candidates(job_id)
    candidates.sort(key=lambda x: x.get("updated_score", 0), reverse=True)
    for rank, c in enumerate(candidates, 1):
        c["rank"] = rank
    return candidates
