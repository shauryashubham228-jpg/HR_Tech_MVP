"""Match Score, Confidence Score, and Engagement Score engines."""

import json
from modules.database import get_candidate, get_engagement


# ── Match Score ───────────────────────────────────────────────────────────────

def _skill_match(candidate_skills: list[str], jd_skills: list[str]) -> float:
    if not jd_skills:
        return 1.0
    candidate_lower = {s.lower() for s in candidate_skills}
    matched = sum(1 for s in jd_skills if s.lower() in candidate_lower)
    return matched / len(jd_skills)


def _experience_match(candidate_exp: float, exp_min: float, exp_max: float) -> float:
    if exp_min == 0 and exp_max == 0:
        return 1.0
    if exp_min <= candidate_exp <= exp_max:
        return 1.0
    if candidate_exp < exp_min:
        gap = exp_min - candidate_exp
        return max(0.0, 1.0 - gap * 0.2)
    # overqualified – small penalty
    gap = candidate_exp - exp_max
    return max(0.5, 1.0 - gap * 0.05)


def _location_match(candidate_loc: str, jd_loc: str) -> float:
    if not jd_loc or jd_loc.lower() in ("remote", "anywhere", ""):
        return 1.0
    return 1.0 if jd_loc.lower() in candidate_loc.lower() else 0.4


def _industry_match(candidate_industry: str, jd_industry: str) -> float:
    if not jd_industry:
        return 1.0
    return 1.0 if jd_industry.lower() in candidate_industry.lower() else 0.6


def _ctc_match(expected_ctc: float, comp_max: float) -> float:
    if not comp_max:
        return 1.0
    if expected_ctc <= comp_max:
        return 1.0
    ratio = comp_max / expected_ctc
    return max(0.3, ratio)


def compute_match_score(candidate: dict, structured_jd: dict,
                        semantic_score: float = 0.0) -> dict:
    """Compute the hybrid match score (structured 70% + semantic 30%)."""
    skill_s = _skill_match(candidate.get("skills", []),
                            structured_jd.get("skills", []))
    exp_s = _experience_match(candidate.get("experience_years", 0),
                               structured_jd.get("experience_min", 0),
                               structured_jd.get("experience_max", 30))
    loc_s = _location_match(candidate.get("location", ""),
                             structured_jd.get("location", ""))
    ind_s = _industry_match(candidate.get("industry", ""),
                             structured_jd.get("industry", ""))
    ctc_s = _ctc_match(candidate.get("expected_ctc", 0),
                        structured_jd.get("compensation_max", 0))

    structured_score = (
        0.35 * skill_s +
        0.25 * exp_s +
        0.15 * loc_s +
        0.15 * ind_s +
        0.10 * ctc_s
    )

    sem_norm = min(1.0, semantic_score / 100)
    final_match = 0.70 * structured_score + 0.30 * sem_norm

    return {
        "skill_score": round(skill_s * 100, 1),
        "experience_score": round(exp_s * 100, 1),
        "location_score": round(loc_s * 100, 1),
        "industry_score": round(ind_s * 100, 1),
        "ctc_score": round(ctc_s * 100, 1),
        "structured_score": round(structured_score * 100, 1),
        "semantic_score": round(sem_norm * 100, 1),
        "match_score": round(final_match * 100, 1),
        "matched_skills": [s for s in structured_jd.get("skills", [])
                           if s.lower() in {x.lower() for x in candidate.get("skills", [])}],
        "missing_skills": [s for s in structured_jd.get("skills", [])
                           if s.lower() not in {x.lower() for x in candidate.get("skills", [])}],
    }


# ── Confidence Score ──────────────────────────────────────────────────────────

def compute_confidence_score(candidate: dict) -> dict:
    """Measure how much evidence supports the candidate's profile."""
    score = 0.0
    evidence = []

    # Project count
    proj_count = len(candidate.get("projects", []))
    proj_score = min(1.0, proj_count / 3)
    score += 0.30 * proj_score
    evidence.append(f"{proj_count} project(s) documented")

    # Work experience coverage
    exp_entries = len(candidate.get("work_experience", []))
    exp_score = min(1.0, exp_entries / 2)
    score += 0.25 * exp_score
    evidence.append(f"{exp_entries} work experience record(s)")

    # About section quality (word count proxy)
    about = candidate.get("about_section", "")
    about_score = min(1.0, len(about.split()) / 60)
    score += 0.20 * about_score
    evidence.append(f"About section: {len(about.split())} words")

    # Skills richness
    skill_count = len(candidate.get("skills", []))
    skill_score = min(1.0, skill_count / 7)
    score += 0.15 * skill_score
    evidence.append(f"{skill_count} skill(s) listed")

    # Education
    edu_score = 1.0 if candidate.get("education") else 0.0
    score += 0.10 * edu_score
    if candidate.get("education"):
        evidence.append("Education documented")

    return {
        "confidence_score": round(score * 100, 1),
        "evidence": evidence,
    }


# ── Engagement Score ──────────────────────────────────────────────────────────

def compute_engagement_score(candidate_id: str) -> dict:
    eng = get_engagement(candidate_id)
    if not eng:
        return {"engagement_score": 50.0, "breakdown": {}}

    return {
        "engagement_score": round(eng["engagement_score"], 1),
        "breakdown": {
            "response_rate": f"{eng['response_rate'] * 100:.0f}%",
            "avg_reply_speed": f"{eng['reply_speed_hours']:.1f} hours",
            "interview_attendance": f"{eng['interview_attendance'] * 100:.0f}%",
            "application_completion": f"{eng['application_completion'] * 100:.0f}%",
        },
    }


# ── Final Ranking Score ───────────────────────────────────────────────────────

def compute_final_score(match_score: float,
                        confidence_score: float,
                        engagement_score: float) -> float:
    """Weighted final ranking score."""
    return round(
        0.60 * match_score +
        0.20 * confidence_score +
        0.20 * engagement_score,
        2,
    )
