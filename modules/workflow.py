"""Recruiter Workflow Tracker."""

from modules.database import (
    update_candidate_status,
    get_job_candidates,
    get_connection,
)

VALID_STATUSES = [
    "Recommended",
    "Contacted",
    "Responded",
    "Screening Complete",
    "Interview Scheduled",
    "Rejected",
    "Selected",
    "Offered",
    "Hired",
]


def move_to_status(job_id: str, candidate_id: str, new_status: str, notes: str = ""):
    if new_status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {new_status}. Must be one of {VALID_STATUSES}")
    update_candidate_status(job_id, candidate_id, new_status, notes)


def get_workflow_history(job_id: str, candidate_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM workflow_history
        WHERE job_id = ? AND candidate_id = ?
        ORDER BY created_at ASC
    """, (job_id, candidate_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_kanban_board(job_id: str) -> dict[str, list[dict]]:
    """Return candidates grouped by workflow status."""
    candidates = get_job_candidates(job_id)
    board: dict[str, list] = {s: [] for s in VALID_STATUSES}
    for c in candidates:
        status = c.get("status", "Recommended")
        if status in board:
            board[status].append(c)
        else:
            board["Recommended"].append(c)
    return board


def get_pipeline_summary(job_id: str) -> dict:
    board = get_kanban_board(job_id)
    return {
        status: len(candidates)
        for status, candidates in board.items()
    }
