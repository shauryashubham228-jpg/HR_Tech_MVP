"""
AI Recruiter Copilot – Gradio UI
Run: python gradio_app.py
"""

import os
import json
import uuid
import pandas as pd
import gradio as gr
from dotenv import load_dotenv

load_dotenv()

# ── Lazy imports for heavy modules ────────────────────────────────────────────
from modules.database import (
    init_db, get_candidate, get_recruiter_memory,
    save_recruiter_memory, get_feedback_analytics,
)
from modules.data_generator import seed_database
from modules.faiss_builder import build_faiss_index, index_exists, load_faiss_index
from modules.jd_intelligence import extract_jd, parse_pdf_jd, format_jd_display
from modules.hybrid_search import run_hybrid_search
from modules.rag_engine import get_match_details, answer_recruiter_question
from modules.question_generator import generate_questions, assess_answer
from modules.reranker import apply_assessment_and_rerank, get_reranked_candidates
from modules.workflow import move_to_status, get_workflow_history, VALID_STATUSES
from modules.submission import generate_submission_report, export_pdf, format_report_text
from modules.feedback import record_outcome, get_analytics_chart, get_funnel_chart, get_reutilization_rate

# ── Global state ──────────────────────────────────────────────────────────────
_state = {
    "job_id": None,
    "structured_jd": None,
    "ranked_candidates": [],
    "selected_candidate": None,
    "generated_questions": [],
    "submission_report": None,
}


def _startup():
    """Initialize DB, seed data, and build FAISS index."""
    init_db()
    candidates = seed_database(500)
    if not index_exists():
        from modules.database import get_all_candidates
        all_c = get_all_candidates()
        build_faiss_index(all_c)
    else:
        load_faiss_index()
    return "✅ System ready. Database seeded with 500 candidates. FAISS index loaded."


# ── Screen 1: JD Upload ───────────────────────────────────────────────────────

def process_jd_text(jd_text: str):
    if not jd_text.strip():
        return "❌ Please enter a job description.", "", gr.update(visible=False)
    structured = extract_jd(jd_text)
    structured["_raw_jd"] = jd_text
    structured["job_id"] = f"JOB-{str(uuid.uuid4())[:6].upper()}"
    _state["structured_jd"] = structured
    display = format_jd_display(structured)
    return f"✅ JD parsed! Job ID: {structured['job_id']}", display, gr.update(visible=True)


def process_jd_pdf(file):
    if file is None:
        return "❌ Please upload a PDF.", "", gr.update(visible=False)
    jd_text = parse_pdf_jd(file.name)
    return process_jd_text(jd_text)


def process_voice_jd(audio):
    """Transcribe voice recording → extract JD → ready to search."""
    if audio is None:
        return "❌ No audio recorded.", "", gr.update(visible=False)
    from modules.jd_intelligence import transcribe_voice
    jd_text = transcribe_voice(audio)
    if jd_text.startswith("Voice transcription failed"):
        return f"❌ {jd_text}", "", gr.update(visible=False)
    return process_jd_text(jd_text)


def run_freetext_search(query: str):
    """
    Plain-English search without a full JD.
    e.g. 'Python developer Bangalore 3 years fintech'
    Builds a minimal structured JD from the query and runs hybrid search.
    """
    if not query.strip():
        return "❌ Enter a search query.", None, gr.update(choices=[])

    # Try LLM parse first; fall back to keyword extraction
    try:
        structured = extract_jd(
            f"Find candidates matching: {query}\n"
            f"Extract role, skills, experience, location, industry from this search query."
        )
    except Exception:
        words = query.split()
        structured = {
            "role": query[:50],
            "skills": words[:4],
            "experience_min": 0,
            "experience_max": 20,
            "location": "",
            "industry": "",
            "compensation_max": 0,
        }

    structured["_raw_jd"] = query
    structured["job_id"] = f"JOB-{str(uuid.uuid4())[:6].upper()}"
    _state["structured_jd"] = structured

    job_id, candidates = run_hybrid_search(structured, top_k=20)
    _state["job_id"] = job_id
    _state["ranked_candidates"] = candidates

    rows = [{
        "Rank": i + 1,
        "Name": c.get("name", ""),
        "Location": c.get("location", ""),
        "Exp (yrs)": c.get("experience_years", 0),
        "Skills": ", ".join(c.get("skills", [])[:4]),
        "Match%": f"{c.get('match_score', 0):.1f}",
        "Final%": f"{c.get('final_score', 0):.1f}",
        "CandidateID": c.get("candidate_id", ""),
    } for i, c in enumerate(candidates)]

    return (
        f"✅ Free-text search found {len(candidates)} candidates",
        pd.DataFrame(rows),
        gr.update(choices=[f"{c['name']} ({c['candidate_id']})" for c in candidates])
    )


# ── Screen 2 & 3: Search & Ranking ───────────────────────────────────────────

def run_search():
    if not _state.get("structured_jd"):
        return "❌ Please parse a JD first.", None, None

    structured = _state["structured_jd"]
    job_id, candidates = run_hybrid_search(structured, top_k=20)
    _state["job_id"] = job_id
    _state["ranked_candidates"] = candidates

    rows = []
    for rank, c in enumerate(candidates, 1):
        rows.append({
            "Rank": rank,
            "Name": c.get("name", ""),
            "Location": c.get("location", ""),
            "Exp (yrs)": c.get("experience_years", 0),
            "Industry": c.get("industry", ""),
            "Skills": ", ".join(c.get("skills", [])[:4]),
            "Match%": f"{c.get('match_score', 0):.1f}",
            "Confidence%": f"{c.get('confidence_score', 0):.1f}",
            "Engagement%": f"{c.get('engagement_score', 0):.1f}",
            "Final%": f"{c.get('final_score', 0):.1f}",
            "CandidateID": c.get("candidate_id", ""),
        })

    df = pd.DataFrame(rows)
    return (
        f"✅ Found {len(candidates)} candidates for Job {job_id}",
        df,
        gr.update(choices=[f"{c['name']} ({c['candidate_id']})" for c in candidates])
    )


def refresh_rankings():
    if not _state.get("job_id"):
        return "❌ No active job.", None
    candidates = get_reranked_candidates(_state["job_id"])
    _state["ranked_candidates"] = candidates
    rows = []
    for c in candidates:
        rows.append({
            "Rank": c.get("rank", ""),
            "Name": c.get("name", ""),
            "Location": c.get("location", ""),
            "Exp (yrs)": c.get("experience_years", 0),
            "Match%": f"{c.get('match_score', 0):.1f}",
            "Updated%": f"{c.get('updated_score', 0):.1f}",
            "Status": c.get("status", "Recommended"),
            "CandidateID": c.get("candidate_id", ""),
        })
    return "✅ Rankings updated", pd.DataFrame(rows)


# ── Screen 4: Match Details ───────────────────────────────────────────────────

def load_match_details(candidate_selection: str):
    if not candidate_selection:
        return "Select a candidate first.", "", "", ""

    cid = candidate_selection.split("(")[-1].rstrip(")")
    candidate = get_candidate(cid)
    if not candidate:
        return "❌ Candidate not found.", "", "", ""

    _state["selected_candidate"] = candidate

    structured = _state.get("structured_jd", {})
    details = get_match_details(cid, structured, candidate)
    gap = details.get("gap_analysis", {})

    matched_text = "\n".join(
        f"✅ {m['requirement']} — {m.get('evidence', '')} [{m.get('strength', '')}]"
        for m in gap.get("matched", [])
    ) or "No matched requirements found."

    missing_text = "\n".join(
        f"❌ {m['requirement']} — Impact: {m.get('impact', '')}. {m.get('note', '')}"
        for m in gap.get("missing", [])
    ) or "No gaps identified."

    summary = details.get("match_summary", "")
    evidence = "\n\n---\n".join(details.get("context_chunks", [])[:3])

    # Store match details in state so Tab 4 can use them for better questions
    _state["last_match_details"] = details
    _state["last_match_gap"] = gap

    return matched_text, missing_text, summary, evidence


def ask_clarification(candidate_selection: str, question: str):
    """
    Recruiter asks a follow-up question about a gap shown in match details.
    RAG answers from the candidate's actual profile text.
    Saved to recruiter_memory as a clarification (not scored).
    Shows in submission report under 'Recruiter Clarifications'.
    """
    if not candidate_selection or not question.strip():
        return "❌ Select a candidate and enter a question.", ""

    cid = candidate_selection.split("(")[-1].rstrip(")")
    candidate = get_candidate(cid) or _state.get("selected_candidate", {})
    structured = _state.get("structured_jd", {})
    job_id = _state.get("job_id", "")

    from modules.rag_engine import answer_recruiter_question
    answer = answer_recruiter_question(cid, candidate, structured, question)

    # Save as clarification in recruiter memory (question + answer, no score)
    save_recruiter_memory(job_id, cid, question, answer, "")

    return f"✅ Clarification saved to candidate memory.", answer


# ── Screen 5: Assessment Panel ────────────────────────────────────────────────

def generate_screening_questions(candidate_selection: str):
    if not candidate_selection:
        return "Select a candidate first.", []

    cid = candidate_selection.split("(")[-1].rstrip(")")
    candidate = get_candidate(cid) or _state.get("selected_candidate", {})
    structured = _state.get("structured_jd", {})

    # Use missing skills from last match detail if available, otherwise compute
    required = structured.get("skills", [])
    candidate_skills = candidate.get("skills", [])
    missing = [s for s in required if s.lower() not in {x.lower() for x in candidate_skills}]

    if not missing:
        missing = required[:3]  # Ask about required skills even if present

    context = candidate.get("about_section", "") + " " + " ".join(
        p.get("description", "") for p in candidate.get("projects", [])[:2]
    )

    questions = generate_questions(missing, structured.get("role", ""), candidate.get("name", ""), context)
    _state["generated_questions"] = questions

    formatted = "\n\n".join([
        f"**Q{i+1}: {q['question']}**\n"
        f"   Targets: {q.get('targets_requirement', '')}\n"
        f"   Potential impact: {q.get('potential_score_impact', '')}\n"
        f"   Why: {q.get('why_important', '')}"
        for i, q in enumerate(questions)
    ])

    question_texts = [q["question"] for q in questions]
    return formatted, gr.update(choices=question_texts)


def _question_already_answered(job_id: str, candidate_id: str, question: str) -> bool:
    """Prevent the same question from being scored twice."""
    from modules.database import get_connection
    conn = get_connection()
    exists = conn.execute(
        "SELECT 1 FROM job_assessments WHERE job_id=? AND candidate_id=? AND question=?",
        (job_id, candidate_id, question)
    ).fetchone()
    conn.close()
    return exists is not None


def _get_current_score(job_id: str, candidate_id: str) -> float:
    """Read updated_score (post-assessment) not original final_score."""
    from modules.database import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT updated_score, final_score FROM job_candidates WHERE job_id=? AND candidate_id=?",
        (job_id, candidate_id)
    ).fetchone()
    conn.close()
    if not row:
        return 70.0
    return row["updated_score"]


def submit_assessment(candidate_selection: str, question: str, answer: str):
    if not candidate_selection or not question or not answer:
        return "❌ Fill all fields.", "", ""

    cid = candidate_selection.split("(")[-1].rstrip(")")
    structured = _state.get("structured_jd", {})
    job_id = _state.get("job_id", "")

    # ── One-time guard: same question cannot be scored twice ─────────────────
    if _question_already_answered(job_id, cid, question):
        cur = _get_current_score(job_id, cid)
        return (
            f"⚠️ This question was already assessed. Current score: {cur:.1f}%",
            "Question already scored — score not changed.",
            f"Score remains: **{cur:.1f}%**"
        )

    matching_q = next(
        (q for q in _state.get("generated_questions", []) if q["question"] == question),
        {"targets_requirement": "General", "question": question}
    )
    requirement = matching_q.get("targets_requirement", "General")

    result = assess_answer(question, answer, structured.get("role", ""), requirement)

    # ── Read updated_score (not final_score) so Q2 builds on Q1 ─────────────
    current_score = _get_current_score(job_id, cid)

    new_score = apply_assessment_and_rerank(
        job_id, cid, question, answer, result, current_score
    )
    # Save full assessment detail including verdict and feedback for the report
    from modules.database import save_assessment
    save_assessment(
        job_id, cid, question, answer,
        result.get("assessment_score", 0),
        result.get("score_impact", 0),
        verdict=result.get("verdict", ""),
        feedback=result.get("feedback", ""),
        targets_requirement=requirement,
    )
    save_recruiter_memory(job_id, cid, question, answer, "")

    assessment_display = (
        f"**Assessment Result**\n\n"
        f"Verdict: **{result.get('verdict', 'N/A')}**\n"
        f"Score: {result.get('assessment_score', 0):.0f}/100\n"
        f"Score Impact: {result.get('score_impact', 0):+.1f} points\n"
        f"New Final Score: **{new_score:.1f}%**\n\n"
        f"---\n"
        f"Relevance: {result.get('relevance', 0)}/100\n"
        f"Completeness: {result.get('completeness', 0)}/100\n"
        f"Evidence Strength: {result.get('evidence_strength', 0)}/100\n\n"
        f"Feedback: _{result.get('feedback', '')}_"
    )

    return (
        f"✅ Assessment submitted. New score: {new_score:.1f}%",
        assessment_display,
        f"Updated Final Score: **{new_score:.1f}%** (was {current_score:.1f}%)"
    )


# ── Screen 6: Workflow Tracker ────────────────────────────────────────────────

def update_workflow_status(candidate_selection: str, new_status: str, notes: str):
    if not candidate_selection or not new_status:
        return "❌ Select candidate and status.", None

    cid = candidate_selection.split("(")[-1].rstrip(")")
    job_id = _state.get("job_id", "")
    move_to_status(job_id, cid, new_status, notes)

    history = get_workflow_history(job_id, cid)
    rows = [{"Status": h["status"], "Notes": h.get("notes", ""), "Time": h["created_at"][:16]}
            for h in history]
    return f"✅ Status updated to: {new_status}", pd.DataFrame(rows)


# ── Screen 7: Recruiter Notes / Memory ───────────────────────────────────────

def load_memory(candidate_selection: str):
    if not candidate_selection:
        return "Select a candidate.", None

    cid = candidate_selection.split("(")[-1].rstrip(")")
    job_id = _state.get("job_id", "")
    memory = get_recruiter_memory(job_id, cid)

    if not memory:
        return "No memory yet for this candidate.", pd.DataFrame()

    rows = [
        {
            "Time": m["created_at"][:16],
            "Question": (m.get("question") or "")[:80],
            "Answer": (m.get("answer") or "")[:100],
            "Notes": (m.get("recruiter_notes") or "")[:80],
        }
        for m in memory
    ]
    return f"Found {len(rows)} memory records.", pd.DataFrame(rows)


def save_note(candidate_selection: str, note: str):
    if not candidate_selection or not note.strip():
        return "❌ Enter a note."
    cid = candidate_selection.split("(")[-1].rstrip(")")
    job_id = _state.get("job_id", "")
    save_recruiter_memory(job_id, cid, "", "", note)
    return "✅ Note saved."


# ── Screen 8: Submission Report ───────────────────────────────────────────────

def generate_report(candidate_selection: str):
    if not candidate_selection:
        return "Select a candidate.", "", None

    cid = candidate_selection.split("(")[-1].rstrip(")")
    job_id = _state.get("job_id", "")

    report = generate_submission_report(job_id, cid)

    # Override displayed score with updated_score (includes assessment uplift)
    from modules.database import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT updated_score FROM job_candidates WHERE job_id=? AND candidate_id=?",
        (job_id, cid)
    ).fetchone()
    conn.close()
    if row:
        report["scores"]["displayed_final_score"] = row["updated_score"]

    _state["submission_report"] = report
    text_report = format_report_text(report)
    return "✅ Report generated.", text_report, gr.update(interactive=True)


def download_pdf():
    report = _state.get("submission_report")
    if not report:
        return None
    path = export_pdf(report)
    return path


# ── Analytics ─────────────────────────────────────────────────────────────────

def load_analytics():
    outcome_chart = get_analytics_chart()
    funnel_chart = get_funnel_chart()
    metrics = get_reutilization_rate()
    summary = (
        f"**Total Candidates:** {metrics['total_candidates']}\n"
        f"**Candidates Engaged:** {metrics['candidates_engaged']}\n"
        f"**Reutilization Rate:** {metrics['reutilization_rate']}%\n"
        f"**Total Hired:** {metrics['total_hired']}\n"
        f"**Hire Rate:** {metrics['hire_rate']}%"
    )
    return summary, outcome_chart, funnel_chart


def record_feedback(candidate_selection: str, outcome: str, notes: str):
    if not candidate_selection or not outcome:
        return "❌ Select candidate and outcome."
    cid = candidate_selection.split("(")[-1].rstrip(")")
    job_id = _state.get("job_id", "")
    record_outcome(job_id, cid, outcome, notes)
    return f"✅ Outcome '{outcome}' recorded for {candidate_selection}"


# ── Build UI ──────────────────────────────────────────────────────────────────

THEME = gr.themes.Soft(
    primary_hue="blue",
    secondary_hue="indigo",
    neutral_hue="slate",
)

CSS = """
.tab-nav button { font-weight: 600; }
.score-box { background: #f0f4ff; border-radius: 8px; padding: 12px; }
footer { display: none !important; }
"""

with gr.Blocks(theme=THEME, css=CSS, title="AI Recruiter Copilot") as app:

    gr.Markdown("""
    # 🎯 AI Recruiter Copilot
    ### Powered by LangChain · Groq Llama 3 70B · FAISS · SQLite
    *Reuse existing candidates before sourcing externally*
    """)

    # Startup
    with gr.Row():
        startup_btn = gr.Button("🚀 Initialize System", variant="primary", size="lg")
        startup_out = gr.Textbox(label="Status", interactive=False)
    startup_btn.click(fn=_startup, outputs=startup_out)

    gr.Markdown("---")

    with gr.Tabs():

        # ── TAB 1: JD Upload ──────────────────────────────────────────────
        with gr.Tab("📄 1. JD Upload"):
            gr.Markdown("""
            ### Upload Job Description
            Three ways to search: paste JD text · upload PDF · speak it · or just type free-text in Tab 2
            """)
            with gr.Row():
                with gr.Column(scale=2):
                    jd_text_input = gr.Textbox(
                        label="Paste Full JD Text",
                        placeholder="Paste your complete job description here...",
                        lines=10,
                    )
                    jd_text_btn = gr.Button("🔍 Parse JD Text", variant="primary")

                    gr.Markdown("**OR upload a PDF:**")
                    jd_pdf_input = gr.File(label="Upload JD PDF", file_types=[".pdf"])
                    jd_pdf_btn = gr.Button("📎 Parse PDF JD")

                    gr.Markdown("**OR record your voice:**")
                    jd_voice_input = gr.Audio(
                        label="Record / Upload Voice JD",
                        type="filepath",
                        sources=["microphone", "upload"],
                    )
                    jd_voice_btn = gr.Button("🎙️ Transcribe & Parse Voice")

                with gr.Column(scale=2):
                    jd_status = gr.Textbox(label="Parse Status", interactive=False)
                    jd_display = gr.Markdown(label="Extracted JD Structure")
                    search_btn = gr.Button("🔎 Find Matching Candidates", variant="primary",
                                          visible=False)

            jd_text_btn.click(fn=process_jd_text, inputs=jd_text_input,
                               outputs=[jd_status, jd_display, search_btn])
            jd_pdf_btn.click(fn=process_jd_pdf, inputs=jd_pdf_input,
                              outputs=[jd_status, jd_display, search_btn])
            jd_voice_btn.click(fn=process_voice_jd, inputs=jd_voice_input,
                                outputs=[jd_status, jd_display, search_btn])

        # ── TAB 2: Search Results ─────────────────────────────────────────
        with gr.Tab("🔍 2. Candidate Search"):
            gr.Markdown("""
            ### Candidate Search
            Run hybrid search after parsing a JD **or** use free-text search directly below.
            """)
            gr.Markdown("**Option A — run after parsing JD in Tab 1:**")
            with gr.Row():
                search_btn2 = gr.Button("🔎 Run Hybrid Search (from JD)", variant="primary")
                refresh_btn = gr.Button("🔄 Refresh Rankings")

            gr.Markdown("---\n**Option B — free-text search (no JD needed):**")
            with gr.Row():
                freetext_input = gr.Textbox(
                    label="Describe what you're looking for",
                    placeholder="e.g. Python developer Bangalore 3 years fintech, or Data Analyst SQL Tableau",
                    lines=2, scale=4,
                )
                freetext_btn = gr.Button("🔎 Search", variant="secondary", scale=1)

            search_status = gr.Textbox(label="Search Status", interactive=False)
            results_table = gr.Dataframe(label="Candidate Results", interactive=False, wrap=True)
            candidate_dropdown = gr.Dropdown(
                label="Select Candidate for Details", choices=[], interactive=True
            )

            search_btn2.click(fn=run_search,
                               outputs=[search_status, results_table, candidate_dropdown])
            refresh_btn.click(fn=refresh_rankings, outputs=[search_status, results_table])
            freetext_btn.click(fn=run_freetext_search, inputs=freetext_input,
                                outputs=[search_status, results_table, candidate_dropdown])

        # ── TAB 3: Match Details (RAG) ────────────────────────────────────
        with gr.Tab("🎯 3. Match Details"):
            gr.Markdown("""
            ### RAG-Powered Match Explanation
            Shows what the AI retrieved from the candidate profile to justify the match.
            Ask clarification questions about any gap — answers are saved and included in the submission report.
            """)
            match_candidate_dd = gr.Dropdown(label="Select Candidate", choices=[], interactive=True)
            match_load_btn = gr.Button("📊 Load Match Details", variant="primary")

            with gr.Row():
                with gr.Column():
                    gr.Markdown("#### ✅ Matched Requirements + Evidence")
                    matched_box = gr.Textbox(lines=8, interactive=False, label="Matched")
                with gr.Column():
                    gr.Markdown("#### ❌ Gaps / Missing Requirements")
                    missing_box = gr.Textbox(lines=8, interactive=False, label="Missing")

            gr.Markdown("#### AI Match Summary")
            match_summary = gr.Markdown()
            gr.Markdown("#### Retrieved Profile Chunks (RAG Context — what the AI actually read)")
            evidence_box = gr.Textbox(lines=5, interactive=False, label="Evidence Chunks")

            gr.Markdown("---\n#### Ask a Clarification Question about any Gap")
            gr.Markdown(
                "_e.g. 'Has this candidate worked with A/B testing even though it's not listed?' "
                "or 'What SQL projects have they done?'_"
            )
            with gr.Row():
                clarif_input = gr.Textbox(
                    label="Your clarification question",
                    placeholder="Ask anything about a gap or missing requirement...",
                    lines=2, scale=4,
                )
                clarif_btn = gr.Button("💬 Get Clarification from Profile", variant="secondary", scale=1)
            clarif_status = gr.Textbox(label="Status", interactive=False)
            clarif_answer = gr.Textbox(
                label="AI Answer (from candidate profile only — no hallucination)",
                lines=5, interactive=False,
            )

            match_load_btn.click(fn=load_match_details, inputs=match_candidate_dd,
                                  outputs=[matched_box, missing_box, match_summary, evidence_box])
            clarif_btn.click(fn=ask_clarification,
                              inputs=[match_candidate_dd, clarif_input],
                              outputs=[clarif_status, clarif_answer])

        # ── TAB 4: Assessment Panel ────────────────────────────────────────
        with gr.Tab("📝 4. Assessment"):
            gr.Markdown("### AI Question Generation & Candidate Assessment")

            assessment_candidate_dd = gr.Dropdown(
                label="Select Candidate", choices=[], interactive=True
            )
            gen_q_btn = gr.Button("💬 Generate Screening Questions", variant="primary")
            questions_display = gr.Markdown(label="Generated Questions")
            question_dd = gr.Dropdown(label="Select Question to Ask", choices=[], interactive=True)

            gr.Markdown("---")
            answer_input = gr.Textbox(
                label="Candidate's Answer",
                placeholder="Enter candidate's response here...",
                lines=5,
            )
            assess_btn = gr.Button("🧠 Assess Answer & Re-Rank", variant="primary")
            assess_status = gr.Textbox(label="Status", interactive=False)
            assess_result = gr.Markdown(label="Assessment Result")
            score_update = gr.Markdown(label="Score Update")

            gen_q_btn.click(
                fn=generate_screening_questions,
                inputs=assessment_candidate_dd,
                outputs=[questions_display, question_dd]
            )
            assess_btn.click(
                fn=submit_assessment,
                inputs=[assessment_candidate_dd, question_dd, answer_input],
                outputs=[assess_status, assess_result, score_update]
            )

        # ── TAB 5: Workflow Tracker ────────────────────────────────────────
        with gr.Tab("📋 5. Workflow"):
            gr.Markdown("### Recruiter Workflow Tracker")
            workflow_candidate_dd = gr.Dropdown(
                label="Select Candidate", choices=[], interactive=True
            )
            with gr.Row():
                status_dd = gr.Dropdown(
                    label="New Status",
                    choices=VALID_STATUSES,
                    value="Contacted",
                    interactive=True,
                )
                status_notes = gr.Textbox(label="Notes", placeholder="Optional notes...")
            update_status_btn = gr.Button("✅ Update Status", variant="primary")
            workflow_status = gr.Textbox(label="Update Status", interactive=False)
            workflow_history_table = gr.Dataframe(label="Workflow History", interactive=False)

            update_status_btn.click(
                fn=update_workflow_status,
                inputs=[workflow_candidate_dd, status_dd, status_notes],
                outputs=[workflow_status, workflow_history_table]
            )

        # ── TAB 6: Recruiter Notes ─────────────────────────────────────────
        with gr.Tab("🗒️ 6. Notes & Memory"):
            gr.Markdown("### Recruiter Memory Layer")
            memory_candidate_dd = gr.Dropdown(
                label="Select Candidate", choices=[], interactive=True
            )
            load_memory_btn = gr.Button("📂 Load Memory", variant="secondary")
            memory_status = gr.Textbox(label="Status", interactive=False)
            memory_table = gr.Dataframe(label="Memory Records", interactive=False)

            gr.Markdown("---")
            note_input = gr.Textbox(
                label="Add Recruiter Note",
                placeholder="Enter your observation or note...",
                lines=3,
            )
            save_note_btn = gr.Button("💾 Save Note")
            note_status = gr.Textbox(label="Note Status", interactive=False)

            load_memory_btn.click(
                fn=load_memory,
                inputs=memory_candidate_dd,
                outputs=[memory_status, memory_table]
            )
            save_note_btn.click(
                fn=save_note,
                inputs=[memory_candidate_dd, note_input],
                outputs=note_status
            )

        # ── TAB 7: Submission Report ───────────────────────────────────────
        with gr.Tab("📤 7. Submission"):
            gr.Markdown("### One-Click Candidate Submission Report")
            submission_candidate_dd = gr.Dropdown(
                label="Select Candidate", choices=[], interactive=True
            )
            gen_report_btn = gr.Button("📋 Generate Submission Report", variant="primary")
            report_status = gr.Textbox(label="Status", interactive=False)
            report_text = gr.Textbox(
                label="Submission Report", lines=25, interactive=False
            )
            pdf_btn = gr.Button("📥 Export PDF", variant="secondary", interactive=False)
            pdf_file = gr.File(label="Download PDF", interactive=False)

            gen_report_btn.click(
                fn=generate_report,
                inputs=submission_candidate_dd,
                outputs=[report_status, report_text, pdf_btn]
            )
            pdf_btn.click(fn=download_pdf, outputs=pdf_file)

        # ── TAB 8: Feedback & Analytics ───────────────────────────────────
        with gr.Tab("📊 8. Analytics"):
            gr.Markdown("### Feedback Loop & Analytics Dashboard")

            with gr.Row():
                fb_candidate_dd = gr.Dropdown(
                    label="Select Candidate", choices=[], interactive=True
                )
                outcome_dd = gr.Dropdown(
                    label="Outcome",
                    choices=["Rejected", "Interviewed", "Selected", "Offered", "Hired"],
                    interactive=True,
                )
                fb_notes = gr.Textbox(label="Notes", placeholder="Optional...")
            record_fb_btn = gr.Button("📝 Record Outcome", variant="primary")
            fb_status = gr.Textbox(label="Status", interactive=False)

            gr.Markdown("---")
            load_analytics_btn = gr.Button("📊 Load Analytics Dashboard")
            metrics_md = gr.Markdown()
            with gr.Row():
                outcome_chart = gr.Plot(label="Outcome Distribution")
                funnel_chart = gr.Plot(label="Recruitment Funnel")

            record_fb_btn.click(
                fn=record_feedback,
                inputs=[fb_candidate_dd, outcome_dd, fb_notes],
                outputs=fb_status
            )
            load_analytics_btn.click(
                fn=load_analytics,
                outputs=[metrics_md, outcome_chart, funnel_chart]
            )

    # ── Sync all candidate dropdowns after any search ─────────────────────
    def _all_dropdowns():
        choices = [f"{c['name']} ({c['candidate_id']})"
                   for c in _state.get("ranked_candidates", [])]
        return [gr.update(choices=choices)] * 6

    for btn in [search_btn2, freetext_btn, search_btn]:
        btn.click(fn=lambda: None, outputs=[]).then(
            fn=_all_dropdowns,
            outputs=[match_candidate_dd, assessment_candidate_dd,
                     workflow_candidate_dd, memory_candidate_dd,
                     submission_candidate_dd, fb_candidate_dd]
        )


def launch():
    print("🚀 Launching AI Recruiter Copilot...")
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    launch()
