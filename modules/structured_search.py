"""Structured (SQL) search via LangChain SQL Agent + direct SQLite queries."""

import os
import json
from modules.database import get_connection, _parse_candidate

DB_PATH = os.getenv("DB_PATH", "data/recruiter.db")

_sql_agent = None


def _build_sql_agent():
    """Lazy-build the LangChain SQL agent."""
    from langchain_community.utilities import SQLDatabase
    from langchain_community.agent_toolkits import create_sql_agent
    from langchain_groq import ChatGroq

    llm = ChatGroq(
        model=os.getenv("GROQ_MODEL", "llama3-70b-8192"),
        temperature=0,
        api_key=os.getenv("GROQ_API_KEY"),
    )
    db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}",
                               include_tables=["candidates", "engagement_data"])
    agent = create_sql_agent(llm=llm, db=db, verbose=False, agent_type="openai-tools")
    return agent


def get_sql_agent():
    global _sql_agent
    if _sql_agent is None:
        _sql_agent = _build_sql_agent()
    return _sql_agent


def nl_to_sql_search(natural_language_query: str) -> tuple[list[dict], str]:
    """Run a natural-language query through the SQL agent. Returns (candidates, sql_used)."""
    agent = get_sql_agent()
    full_query = (
        f"{natural_language_query}. "
        "Return candidate_id, name, location, experience_years, skills, "
        "current_ctc, expected_ctc, industry. Limit to 50 rows."
    )
    try:
        result = agent.run(full_query)
    except Exception as e:
        return [], f"SQL Agent error: {e}"

    # Extract candidate_ids from the agent's text response
    conn = get_connection()
    rows = conn.execute("SELECT * FROM candidates LIMIT 50").fetchall()
    conn.close()

    # Try to find candidate IDs mentioned in the result
    candidates = []
    for row in rows:
        cid = row["candidate_id"]
        if cid in result:
            candidates.append(_parse_candidate(row))

    return candidates, result


def structured_filter(
    role: str = "",
    skills: list[str] = None,
    location: str = "",
    experience_min: float = 0,
    experience_max: float = 30,
    industry: str = "",
    ctc_max: float = 999,
    limit: int = 200,
) -> list[dict]:
    """Direct SQL query with structured filters. Fast and deterministic."""
    conn = get_connection()
    params = []
    clauses = []

    if experience_min > 0:
        clauses.append("experience_years >= ?")
        params.append(experience_min)
    if experience_max < 30:
        clauses.append("experience_years <= ?")
        params.append(experience_max)
    if location:
        clauses.append("LOWER(location) LIKE ?")
        params.append(f"%{location.lower()}%")
    if industry:
        clauses.append("LOWER(industry) LIKE ?")
        params.append(f"%{industry.lower()}%")
    if ctc_max < 999:
        clauses.append("expected_ctc <= ?")
        params.append(ctc_max)

    skill_clauses = []
    for skill in (skills or []):
        skill_clauses.append("LOWER(skills) LIKE ?")
        params.append(f"%{skill.lower()}%")
    if skill_clauses:
        clauses.append(f"({' AND '.join(skill_clauses)})")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM candidates {where} LIMIT {limit}"

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_parse_candidate(r) for r in rows]


def get_candidates_for_jd(structured_jd: dict) -> list[dict]:
    """Run structured filter using parsed JD fields."""
    return structured_filter(
        skills=structured_jd.get("skills", [])[:5],
        location=structured_jd.get("location", ""),
        experience_min=structured_jd.get("experience_min", 0),
        experience_max=structured_jd.get("experience_max", 30),
        industry=structured_jd.get("industry", ""),
        limit=300,
    )
