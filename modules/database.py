"""SQLite database layer for AI Recruiter Copilot."""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "data/recruiter.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    c.executescript("""
    CREATE TABLE IF NOT EXISTS candidates (
        candidate_id    TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        email           TEXT,
        phone           TEXT,
        location        TEXT,
        experience_years REAL,
        current_ctc     REAL,
        expected_ctc    REAL,
        skills          TEXT,
        about_section   TEXT,
        projects        TEXT,
        work_experience TEXT,
        industry        TEXT,
        education       TEXT,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS engagement_data (
        candidate_id            TEXT PRIMARY KEY,
        response_rate           REAL,
        reply_speed_hours       REAL,
        interview_attendance    REAL,
        application_completion  REAL,
        engagement_score        REAL,
        FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
    );

    CREATE TABLE IF NOT EXISTS jobs (
        job_id          TEXT PRIMARY KEY,
        jd_text         TEXT,
        structured_jd   TEXT,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS job_candidates (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id              TEXT,
        candidate_id        TEXT,
        status              TEXT DEFAULT 'Recommended',
        match_score         REAL DEFAULT 0,
        confidence_score    REAL DEFAULT 0,
        engagement_score    REAL DEFAULT 0,
        final_score         REAL DEFAULT 0,
        assessment_score    REAL DEFAULT 0,
        updated_score       REAL DEFAULT 0,
        created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at          TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(job_id, candidate_id)
    );

    CREATE TABLE IF NOT EXISTS recruiter_memory (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          TEXT,
        candidate_id    TEXT,
        question        TEXT,
        answer          TEXT,
        recruiter_notes TEXT,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS workflow_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          TEXT,
        candidate_id    TEXT,
        status          TEXT,
        notes           TEXT,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS feedback (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          TEXT,
        candidate_id    TEXT,
        outcome         TEXT,
        notes           TEXT,
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS job_assessments (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          TEXT,
        candidate_id    TEXT,
        question        TEXT,
        answer          TEXT,
        assessment_score REAL DEFAULT 0,
        score_impact    REAL DEFAULT 0,
        verdict         TEXT DEFAULT '',
        feedback        TEXT DEFAULT '',
        targets_requirement TEXT DEFAULT '',
        created_at      TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print("✅ Database initialized")


# ── Candidate helpers ─────────────────────────────────────────────────────────

def insert_candidate(c: dict):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO candidates
        (candidate_id, name, email, phone, location, experience_years,
         current_ctc, expected_ctc, skills, about_section, projects,
         work_experience, industry, education)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        c["candidate_id"], c["name"], c.get("email", ""), c.get("phone", ""),
        c["location"], c["experience_years"], c["current_ctc"], c["expected_ctc"],
        json.dumps(c["skills"]), c["about_section"],
        json.dumps(c["projects"]), json.dumps(c["work_experience"]),
        c["industry"], c.get("education", "")
    ))
    conn.commit()
    conn.close()


def insert_engagement(e: dict):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO engagement_data
        (candidate_id, response_rate, reply_speed_hours,
         interview_attendance, application_completion, engagement_score)
        VALUES (?,?,?,?,?,?)
    """, (
        e["candidate_id"], e["response_rate"], e["reply_speed_hours"],
        e["interview_attendance"], e["application_completion"], e["engagement_score"]
    ))
    conn.commit()
    conn.close()


def _parse_candidate(row: sqlite3.Row) -> dict:
    d = dict(row)
    for key in ("skills", "projects", "work_experience"):
        if isinstance(d.get(key), str):
            try:
                d[key] = json.loads(d[key])
            except Exception:
                d[key] = []
    return d


def get_candidate(candidate_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    conn.close()
    return _parse_candidate(row) if row else None


def get_all_candidates() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM candidates").fetchall()
    conn.close()
    return [_parse_candidate(r) for r in rows]


def get_candidates_by_ids(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    placeholders = ",".join("?" * len(ids))
    conn = get_connection()
    rows = conn.execute(
        f"SELECT * FROM candidates WHERE candidate_id IN ({placeholders})", ids
    ).fetchall()
    conn.close()
    return [_parse_candidate(r) for r in rows]


def get_engagement(candidate_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM engagement_data WHERE candidate_id = ?", (candidate_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Job helpers ───────────────────────────────────────────────────────────────

def save_job(job_id: str, jd_text: str, structured_jd: dict):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO jobs (job_id, jd_text, structured_jd) VALUES (?,?,?)",
        (job_id, jd_text, json.dumps(structured_jd))
    )
    conn.commit()
    conn.close()


def get_job(job_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["structured_jd"] = json.loads(d["structured_jd"]) if d["structured_jd"] else {}
    return d


# ── Job-Candidate helpers ─────────────────────────────────────────────────────

def upsert_job_candidate(job_id: str, candidate_id: str, scores: dict):
    conn = get_connection()
    conn.execute("""
        INSERT INTO job_candidates
        (job_id, candidate_id, match_score, confidence_score,
         engagement_score, final_score, updated_score)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(job_id, candidate_id) DO UPDATE SET
          match_score      = excluded.match_score,
          confidence_score = excluded.confidence_score,
          engagement_score = excluded.engagement_score,
          final_score      = excluded.final_score,
          updated_score    = excluded.final_score,
          updated_at       = CURRENT_TIMESTAMP
    """, (
        job_id, candidate_id,
        scores.get("match_score", 0),
        scores.get("confidence_score", 0),
        scores.get("engagement_score", 0),
        scores.get("final_score", 0),
        scores.get("final_score", 0),
    ))
    conn.commit()
    conn.close()


def update_candidate_status(job_id: str, candidate_id: str, status: str, notes: str = ""):
    conn = get_connection()
    conn.execute("""
        UPDATE job_candidates SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE job_id = ? AND candidate_id = ?
    """, (status, job_id, candidate_id))
    conn.execute("""
        INSERT INTO workflow_history (job_id, candidate_id, status, notes)
        VALUES (?,?,?,?)
    """, (job_id, candidate_id, status, notes))
    conn.commit()
    conn.close()


def update_assessment_score(job_id: str, candidate_id: str, new_score: float):
    conn = get_connection()
    conn.execute("""
        UPDATE job_candidates
        SET assessment_score = ?, updated_score = ?, updated_at = CURRENT_TIMESTAMP
        WHERE job_id = ? AND candidate_id = ?
    """, (new_score, new_score, job_id, candidate_id))
    conn.commit()
    conn.close()


def get_job_candidates(job_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT jc.*, c.name, c.location, c.experience_years,
               c.skills, c.industry, c.about_section
        FROM job_candidates jc
        JOIN candidates c ON jc.candidate_id = c.candidate_id
        WHERE jc.job_id = ?
        ORDER BY jc.updated_score DESC
    """, (job_id,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("skills"), str):
            d["skills"] = json.loads(d["skills"])
        result.append(d)
    return result


# ── Memory helpers ────────────────────────────────────────────────────────────

def save_recruiter_memory(job_id: str, candidate_id: str, question: str,
                          answer: str, notes: str = ""):
    conn = get_connection()
    conn.execute("""
        INSERT INTO recruiter_memory
        (job_id, candidate_id, question, answer, recruiter_notes)
        VALUES (?,?,?,?,?)
    """, (job_id, candidate_id, question, answer, notes))
    conn.commit()
    conn.close()


def get_recruiter_memory(job_id: str, candidate_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM recruiter_memory
        WHERE job_id = ? AND candidate_id = ?
        ORDER BY created_at DESC
    """, (job_id, candidate_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Assessment helpers ────────────────────────────────────────────────────────

def save_assessment(job_id: str, candidate_id: str, question: str,
                    answer: str, assessment_score: float, score_impact: float,
                    verdict: str = "", feedback: str = "", targets_requirement: str = ""):
    conn = get_connection()
    conn.execute("""
        INSERT INTO job_assessments
        (job_id, candidate_id, question, answer, assessment_score, score_impact,
         verdict, feedback, targets_requirement)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (job_id, candidate_id, question, answer, assessment_score, score_impact,
          verdict, feedback, targets_requirement))
    conn.commit()
    conn.close()


def get_assessments(job_id: str, candidate_id: str) -> list[dict]:
    """Return all assessed Q&A with verdicts and score impacts for a candidate+job."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT question, answer, assessment_score, score_impact,
               verdict, feedback, targets_requirement, created_at
        FROM job_assessments
        WHERE job_id=? AND candidate_id=?
        ORDER BY created_at
    """, (job_id, candidate_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Feedback helpers ──────────────────────────────────────────────────────────

def save_feedback(job_id: str, candidate_id: str, outcome: str, notes: str = ""):
    conn = get_connection()
    conn.execute("""
        INSERT INTO feedback (job_id, candidate_id, outcome, notes)
        VALUES (?,?,?,?)
    """, (job_id, candidate_id, outcome, notes))
    conn.commit()
    conn.close()


def get_feedback_analytics() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT outcome, COUNT(*) as count FROM feedback GROUP BY outcome
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_feedback() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.*, c.name FROM feedback f
        JOIN candidates c ON f.candidate_id = c.candidate_id
        ORDER BY f.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
