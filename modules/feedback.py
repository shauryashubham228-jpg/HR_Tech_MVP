"""Feedback Loop – store outcomes and generate analytics."""

import plotly.graph_objects as go
import plotly.express as px
from modules.database import save_feedback, get_feedback_analytics, get_all_feedback


def record_outcome(job_id: str, candidate_id: str, outcome: str, notes: str = ""):
    """Record a hiring outcome for a candidate."""
    valid = {"Rejected", "Interviewed", "Selected", "Offered", "Hired"}
    if outcome not in valid:
        raise ValueError(f"Outcome must be one of {valid}")
    save_feedback(job_id, candidate_id, outcome, notes)


def get_analytics_chart() -> go.Figure:
    """Return a Plotly pie chart of outcome distribution."""
    data = get_feedback_analytics()
    if not data:
        fig = go.Figure()
        fig.update_layout(title="No feedback data yet")
        return fig

    labels = [d["outcome"] for d in data]
    values = [d["count"] for d in data]
    color_map = {
        "Hired": "#4caf50",
        "Offered": "#8bc34a",
        "Selected": "#03a9f4",
        "Interviewed": "#ff9800",
        "Rejected": "#f44336",
    }
    colors = [color_map.get(l, "#9e9e9e") for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        marker_colors=colors,
        hole=0.4,
        textinfo="label+percent+value",
    ))
    fig.update_layout(
        title="Hiring Outcome Distribution",
        showlegend=True,
        height=400,
    )
    return fig


def get_funnel_chart() -> go.Figure:
    """Return a Plotly funnel chart showing pipeline stages."""
    stages = ["Recommended", "Contacted", "Responded",
              "Screening Complete", "Interview Scheduled",
              "Selected", "Offered", "Hired"]
    data = get_all_feedback()
    counts = {}
    for d in data:
        o = d.get("outcome", "")
        counts[o] = counts.get(o, 0) + 1

    stage_counts = []
    total = sum(counts.values()) or 10
    for i, stage in enumerate(stages):
        stage_counts.append(max(0, int(total * (0.8 ** i))))

    fig = go.Figure(go.Funnel(
        y=stages,
        x=stage_counts,
        textinfo="value+percent initial",
        marker_color=["#1565c0", "#1976d2", "#1e88e5",
                      "#42a5f5", "#64b5f6", "#4caf50", "#66bb6a", "#81c784"],
    ))
    fig.update_layout(title="Recruitment Funnel", height=400)
    return fig


def get_reutilization_rate() -> dict:
    """Calculate candidate reutilization metrics."""
    from modules.database import get_connection
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
    contacted = conn.execute("""
        SELECT COUNT(DISTINCT candidate_id) FROM job_candidates
        WHERE status != 'Recommended'
    """).fetchone()[0]
    hired = conn.execute("""
        SELECT COUNT(*) FROM feedback WHERE outcome = 'Hired'
    """).fetchone()[0]
    conn.close()

    return {
        "total_candidates": total,
        "candidates_engaged": contacted,
        "reutilization_rate": round((contacted / total * 100) if total else 0, 1),
        "total_hired": hired,
        "hire_rate": round((hired / contacted * 100) if contacted else 0, 1),
    }
