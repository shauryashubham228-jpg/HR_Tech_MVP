"""One-Click Candidate Submission Report Generator (PDF + text)."""

import os
from datetime import datetime
from modules.database import (
    get_candidate,
    get_recruiter_memory,
    get_assessments,
    get_job,
    get_connection,
)

EXPORT_PATH = os.getenv("EXPORT_PATH", "exports")


def _get_job_candidate_scores(job_id: str, candidate_id: str) -> dict:
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM job_candidates WHERE job_id = ? AND candidate_id = ?
    """, (job_id, candidate_id)).fetchone()
    conn.close()
    return dict(row) if row else {}


def generate_submission_report(job_id: str, candidate_id: str) -> dict:
    """Build full submission report including assessments, notes, and match evidence."""
    candidate = get_candidate(candidate_id)
    job = get_job(job_id)
    scores = _get_job_candidate_scores(job_id, candidate_id)
    memory = get_recruiter_memory(job_id, candidate_id)
    assessments = get_assessments(job_id, candidate_id)

    structured_jd = job.get("structured_jd", {}) if job else {}
    required_skills = structured_jd.get("skills", [])
    candidate_skills = candidate.get("skills", [])
    matched_skills = [s for s in required_skills
                      if s.lower() in {x.lower() for x in candidate_skills}]
    missing_skills = [s for s in required_skills
                      if s.lower() not in {x.lower() for x in candidate_skills}]

    # Pull matching evidence from RAG (actual profile text proving the match)
    match_evidence = []
    try:
        from modules.rag_engine import get_match_details
        details = get_match_details(candidate_id, structured_jd, candidate)
        gap = details.get("gap_analysis", {})
        match_evidence = [
            {
                "requirement": m.get("requirement", ""),
                "evidence": m.get("evidence", ""),
                "strength": m.get("strength", ""),
            }
            for m in gap.get("matched", [])
        ]
        # Also grab the raw retrieved chunks
        context_chunks = details.get("context_chunks", [])[:4]
    except Exception:
        context_chunks = []

    # Recruiter notes (pure observations, no question)
    recruiter_notes = list({
        m["recruiter_notes"] for m in memory
        if m.get("recruiter_notes", "").strip()
    })

    # Clarifications: recruiter asked a follow-up question in match details tab
    # (stored in recruiter_memory with question+answer but NOT in job_assessments)
    assessed_questions = {a["question"] for a in assessments}
    clarifications = [
        {"question": m["question"], "answer": m["answer"]}
        for m in memory
        if m.get("question", "").strip()
        and m.get("answer", "").strip()
        and m["question"] not in assessed_questions   # exclude scored Q&A
    ]

    # Scored assessment Q&A with full verdict + feedback + score impact
    assessed_qa = [
        {
            "question": a["question"],
            "answer": a["answer"],
            "targets": a.get("targets_requirement", ""),
            "verdict": a.get("verdict", ""),
            "feedback": a.get("feedback", ""),
            "assessment_score": a.get("assessment_score", 0),
            "score_impact": a.get("score_impact", 0),
        }
        for a in assessments
    ]

    # Score after all assessments
    final_display = scores.get("updated_score") or scores.get("final_score", 0)
    total_impact = sum(a.get("score_impact", 0) for a in assessments)

    return {
        "report_id": f"RPT-{job_id}-{candidate_id}",
        "generated_at": datetime.now().isoformat(),
        "candidate": {
            "name": candidate.get("name"),
            "location": candidate.get("location"),
            "experience_years": candidate.get("experience_years"),
            "industry": candidate.get("industry"),
            "current_ctc": candidate.get("current_ctc"),
            "expected_ctc": candidate.get("expected_ctc"),
            "education": candidate.get("education"),
            "skills": candidate_skills,
            "about": candidate.get("about_section"),
        },
        "job": {
            "role": structured_jd.get("role", "N/A"),
            "location": structured_jd.get("location", "N/A"),
            "experience": f"{structured_jd.get('experience_min', 0)}-{structured_jd.get('experience_max', 0)} yrs",
        },
        "scores": {
            "match_score": scores.get("match_score", 0),
            "confidence_score": scores.get("confidence_score", 0),
            "engagement_score": scores.get("engagement_score", 0),
            "final_score": scores.get("final_score", 0),
            "displayed_final_score": final_display,
            "assessment_uplift": round(total_impact, 1),
        },
        "match_analysis": {
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "match_rate": f"{len(matched_skills)}/{len(required_skills)}",
        },
        "match_evidence": match_evidence,
        "context_chunks": context_chunks,
        "top_projects": candidate.get("projects", [])[:3],
        "work_experience": candidate.get("work_experience", [])[:3],
        "recruiter_notes": recruiter_notes,
        "clarifications": clarifications,           # unscored follow-up Q&A from match details
        "assessed_qa": assessed_qa,                 # scored Q&A with verdicts + feedback
    }


def export_pdf(report: dict) -> str:
    """Export submission report as PDF. Returns file path."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )
    from reportlab.lib.units import cm

    os.makedirs(EXPORT_PATH, exist_ok=True)
    filename = os.path.join(
        EXPORT_PATH,
        f"submission_{report['report_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )

    doc = SimpleDocTemplate(filename, pagesize=A4,
                            leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Header
    header_style = ParagraphStyle("Header", parent=styles["Heading1"],
                                  textColor=colors.HexColor("#1a1a2e"), fontSize=18)
    sub_style = ParagraphStyle("Sub", parent=styles["Normal"],
                               textColor=colors.HexColor("#4a4a6a"), fontSize=10)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14)
    section_style = ParagraphStyle("Section", parent=styles["Heading2"],
                                   textColor=colors.HexColor("#16213e"), fontSize=13)

    story.append(Paragraph("🎯 Candidate Submission Report", header_style))
    story.append(Paragraph(
        f"Generated: {report['generated_at'][:16]} | Report: {report['report_id']}",
        sub_style
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e0e0e0")))
    story.append(Spacer(1, 0.3*cm))

    # Candidate overview
    c = report["candidate"]
    story.append(Paragraph("Candidate Overview", section_style))
    overview_data = [
        ["Name", c.get("name", "")],
        ["Location", c.get("location", "")],
        ["Experience", f"{c.get('experience_years', 0)} years"],
        ["Industry", c.get("industry", "")],
        ["Current CTC", f"₹{c.get('current_ctc', 0):.1f} LPA"],
        ["Expected CTC", f"₹{c.get('expected_ctc', 0):.1f} LPA"],
        ["Education", c.get("education", "")],
    ]
    t = Table(overview_data, colWidths=[4*cm, 13*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4ff")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d0d0")),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4*cm))

    # Scores
    story.append(Paragraph("Match Scores", section_style))
    s = report["scores"]
    final = s.get("displayed_final_score") or s.get("final_score", 0)
    uplift = s.get("assessment_uplift", 0)
    score_data = [
        ["Match Score", f"{s.get('match_score', 0):.1f}%",
         "Confidence", f"{s.get('confidence_score', 0):.1f}%"],
        ["Engagement Score", f"{s.get('engagement_score', 0):.1f}%",
         "Assessment Uplift", f"{uplift:+.1f} pts"],
        ["Base Final Score", f"{s.get('final_score', 0):.1f}%",
         "FINAL SCORE", f"{final:.1f}%"],
    ]
    st = Table(score_data, colWidths=[4*cm, 3*cm, 4*cm, 3*cm])
    st.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8f5e9")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c8e6c9")),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(st)
    story.append(Spacer(1, 0.4*cm))

    # Matching Evidence (RAG)
    m = report["match_analysis"]
    story.append(Paragraph("Matching Evidence", section_style))
    if report.get("match_evidence"):
        for ev in report["match_evidence"]:
            story.append(Paragraph(f"<b>✓ {ev['requirement']}</b>", body_style))
            if ev.get("evidence"):
                story.append(Paragraph(f"&nbsp;&nbsp;Evidence: {ev['evidence']}", body_style))
            if ev.get("strength"):
                story.append(Paragraph(f"&nbsp;&nbsp;Strength: {ev['strength']}", sub_style))
            story.append(Spacer(1, 0.1*cm))
    else:
        for skill in m.get("matched_skills", []):
            story.append(Paragraph(f"✓ {skill}", body_style))
    if m.get("missing_skills"):
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("<b>Gaps Identified:</b>", body_style))
        for skill in m.get("missing_skills", []):
            story.append(Paragraph(f"✗ {skill}", body_style))
    story.append(Spacer(1, 0.4*cm))

    # Retrieved profile sections (RAG context)
    if report.get("context_chunks"):
        story.append(Paragraph("Retrieved Profile Sections (RAG Context)", section_style))
        for i, chunk in enumerate(report["context_chunks"], 1):
            story.append(Paragraph(f"<b>[{i}]</b> {chunk[:350]}", body_style))
            story.append(Spacer(1, 0.15*cm))
        story.append(Spacer(1, 0.3*cm))

    # About
    story.append(Paragraph("About Candidate", section_style))
    story.append(Paragraph(c.get("about", ""), body_style))
    story.append(Spacer(1, 0.4*cm))

    # Key Projects
    story.append(Paragraph("Key Projects", section_style))
    for proj in report.get("top_projects", []):
        story.append(Paragraph(f"<b>{proj.get('title', '')}</b>", body_style))
        story.append(Paragraph(proj.get("description", ""), body_style))
        story.append(Paragraph(
            f"Skills: {', '.join(proj.get('skills_used', []))} | Impact: {proj.get('impact', '')}",
            sub_style
        ))
        story.append(Spacer(1, 0.2*cm))

    # Recruiter clarifications from match details tab
    if report.get("clarifications"):
        story.append(Paragraph("Recruiter Clarifications (Match Details Follow-up)", section_style))
        for i, cl in enumerate(report["clarifications"], 1):
            story.append(Paragraph(f"<b>Q{i}:</b> {cl['question']}", body_style))
            story.append(Paragraph(f"<b>A{i}:</b> {cl['answer'][:400]}", body_style))
            story.append(Spacer(1, 0.15*cm))
        story.append(Spacer(1, 0.3*cm))

    # Screening Q&A with assessment verdicts
    if report.get("assessed_qa"):
        story.append(Paragraph("Screening Q&A with AI Assessment", section_style))
        for i, qa in enumerate(report["assessed_qa"], 1):
            story.append(Paragraph(
                f"<b>Q{i}: {qa['question']}</b>  <i>[Targets: {qa.get('targets','')}]</i>",
                body_style
            ))
            story.append(Paragraph(f"Answer: {qa['answer'][:300]}", body_style))
            verdict_color = "#2e7d32" if "strong" in qa.get("verdict","").lower() or "good" in qa.get("verdict","").lower() else "#c62828"
            story.append(Paragraph(
                f"Verdict: <b>{qa.get('verdict','N/A')}</b>  |  "
                f"Score: {qa.get('assessment_score',0):.0f}/100  |  "
                f"Impact: {qa.get('score_impact',0):+.1f} pts",
                body_style
            ))
            if qa.get("feedback"):
                story.append(Paragraph(f"<i>AI Feedback: {qa['feedback']}</i>", sub_style))
            story.append(Spacer(1, 0.25*cm))

    # Recruiter Notes
    if report.get("recruiter_notes"):
        story.append(Paragraph("Recruiter Notes", section_style))
        for note in report["recruiter_notes"]:
            if note:
                story.append(Paragraph(f"• {note}", body_style))
        story.append(Spacer(1, 0.3*cm))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e0e0e0")))
    story.append(Paragraph(
        "Generated by AI Recruiter Copilot – TalentXO", sub_style
    ))

    doc.build(story)
    print(f"✅ PDF exported: {filename}")
    return filename


def format_report_text(report: dict) -> str:
    """Full human-readable submission report with evidence, Q&A verdicts, and notes."""
    c = report["candidate"]
    s = report["scores"]
    m = report["match_analysis"]
    final = s.get("displayed_final_score") or s.get("final_score", 0)
    uplift = s.get("assessment_uplift", 0)

    lines = [
        f"{'='*62}",
        f"  CANDIDATE SUBMISSION REPORT",
        f"  {report['report_id']}  |  {report['generated_at'][:16]}",
        f"{'='*62}",
        "",
        f"CANDIDATE  : {c.get('name')}",
        f"Location   : {c.get('location')}   |   Experience: {c.get('experience_years')} yrs",
        f"Industry   : {c.get('industry')}",
        f"Education  : {c.get('education', 'N/A')}",
        f"Current CTC: ₹{c.get('current_ctc', 0)} LPA   Expected: ₹{c.get('expected_ctc', 0)} LPA",
        "",
        f"ROLE APPLIED: {report['job'].get('role')}  |  {report['job'].get('location')}  |  {report['job'].get('experience')}",
        "",
        f"{'─'*62}",
        f"SCORES",
        f"{'─'*62}",
        f"  Match Score      : {s.get('match_score', 0):.1f}%",
        f"  Confidence Score : {s.get('confidence_score', 0):.1f}%",
        f"  Engagement Score : {s.get('engagement_score', 0):.1f}%",
        f"  Base Final Score : {s.get('final_score', 0):.1f}%",
        f"  Assessment Uplift: {uplift:+.1f} pts  (from {len(report.get('assessed_qa', []))} question(s))",
        f"  FINAL SCORE      : {final:.1f}%",
        "",
    ]

    # ── Matching evidence from RAG ────────────────────────────────────────────
    lines += [f"{'─'*62}", "MATCHING EVIDENCE (AI-retrieved from profile)", f"{'─'*62}"]
    if report.get("match_evidence"):
        for ev in report["match_evidence"]:
            lines.append(f"  ✅ {ev['requirement']}")
            if ev.get("evidence"):
                lines.append(f"     Evidence  : {ev['evidence']}")
            if ev.get("strength"):
                lines.append(f"     Strength  : {ev['strength']}")
    else:
        lines += [f"  ✓ {sk}" for sk in m.get("matched_skills", [])]

    if m.get("missing_skills"):
        lines += ["", "  GAPS / MISSING:"]
        for sk in m["missing_skills"]:
            lines.append(f"  ✗ {sk}")
    lines.append("")

    # ── Raw profile chunks retrieved (RAG context) ────────────────────────────
    if report.get("context_chunks"):
        lines += [f"{'─'*62}", "RETRIEVED PROFILE SECTIONS (RAG Context)", f"{'─'*62}"]
        for i, chunk in enumerate(report["context_chunks"], 1):
            lines.append(f"  [{i}] {chunk[:300]}")
        lines.append("")

    # ── Key projects ──────────────────────────────────────────────────────────
    if report.get("top_projects"):
        lines += [f"{'─'*62}", "KEY PROJECTS", f"{'─'*62}"]
        for p in report["top_projects"]:
            lines.append(f"  {p.get('title', '')}")
            lines.append(f"  {p.get('description', '')[:200]}")
            lines.append(f"  Skills: {', '.join(p.get('skills_used', []))}  |  Impact: {p.get('impact', '')}")
            lines.append("")

    # ── Recruiter clarifications (unscored follow-ups from match details) ────────
    if report.get("clarifications"):
        lines += [f"{'─'*62}", "RECRUITER CLARIFICATIONS (from Match Details)", f"{'─'*62}"]
        for i, cl in enumerate(report["clarifications"], 1):
            lines.append(f"  Q{i}: {cl['question']}")
            lines.append(f"  A{i}: {cl['answer'][:400]}")
            lines.append("")

    # ── Screening Q&A with assessment verdicts ────────────────────────────────
    if report.get("assessed_qa"):
        lines += [f"{'─'*62}", "SCREENING Q&A  (with AI Assessment)", f"{'─'*62}"]
        for i, qa in enumerate(report["assessed_qa"], 1):
            lines.append(f"  Q{i}: {qa['question']}")
            lines.append(f"  Targets: {qa.get('targets', '')}")
            lines.append(f"  Answer : {qa['answer'][:300]}")
            lines.append(f"  Verdict: {qa.get('verdict', 'N/A')}  |  Score: {qa.get('assessment_score', 0):.0f}/100  |  Impact: {qa.get('score_impact', 0):+.1f} pts")
            if qa.get("feedback"):
                lines.append(f"  AI Feedback: {qa['feedback']}")
            lines.append("")

    # ── Recruiter notes ───────────────────────────────────────────────────────
    if report.get("recruiter_notes"):
        lines += [f"{'─'*62}", "RECRUITER NOTES", f"{'─'*62}"]
        for note in report["recruiter_notes"]:
            lines.append(f"  • {note}")
        lines.append("")

    lines += [f"{'='*62}", "Generated by AI Recruiter Copilot – TalentXO"]
    return "\n".join(lines)
