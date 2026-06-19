"""AI Question Generator for gap-filling recruiter qualification questions."""

import os
import json
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

GROQ_MODEL_FALLBACKS = [
    "llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
    "llama3-8b-8192", "gemma2-9b-it",
]
GROQ_MODEL = os.getenv("GROQ_MODEL", GROQ_MODEL_FALLBACKS[0])
_llm = None

QUESTION_PROMPT = PromptTemplate(
    input_variables=["missing_skills", "role", "candidate_name", "candidate_context"],
    template="""You are an expert recruiter helping assess a candidate for a {role} position.

The following requirements are missing or unclear in the candidate's profile:
{missing_skills}

Candidate context:
{candidate_context}

Generate 3-5 targeted screening questions to assess the missing requirements.
For each question, estimate the potential score improvement if answered positively.

Return a JSON array:
[
  {{
    "question": "...",
    "targets_requirement": "...",
    "potential_score_impact": "+X%",
    "why_important": "..."
  }}
]

Return ONLY valid JSON. No markdown.
""",
)

ASSESSMENT_PROMPT = PromptTemplate(
    input_variables=["question", "answer", "role", "requirement"],
    template="""You are an expert recruiter evaluating a candidate's answer.

Role: {role}
Requirement being assessed: {requirement}
Question: {question}
Candidate's Answer: {answer}

Evaluate the answer on these dimensions (0-100 each):
- Relevance: Does the answer address the question?
- Completeness: Is the answer detailed enough?
- Evidence Strength: Does the answer include concrete examples?
- Overall Quality: How compelling is this answer?

Return a JSON object:
{{
  "relevance": <0-100>,
  "completeness": <0-100>,
  "evidence_strength": <0-100>,
  "overall_quality": <0-100>,
  "assessment_score": <0-100>,
  "score_impact": <-5 to +10>,
  "feedback": "One sentence feedback",
  "verdict": "Strong / Moderate / Weak"
}}

Return ONLY valid JSON. No markdown.
""",
)


def _get_llm():
    global _llm
    if _llm is None:
        api_key = os.getenv("GROQ_API_KEY")
        for model in GROQ_MODEL_FALLBACKS:
            try:
                candidate = ChatGroq(model=model, temperature=0.3, api_key=api_key)
                candidate.invoke("hi")
                _llm = candidate
                break
            except Exception as e:
                if "decommissioned" in str(e).lower() or "400" in str(e):
                    continue
                raise
    return _llm


def generate_questions(missing_skills: list[str], role: str,
                       candidate_name: str, candidate_context: str) -> list[dict]:
    """Generate qualification questions for missing JD requirements."""
    llm = _get_llm()
    prompt = QUESTION_PROMPT.format(
        missing_skills="\n".join(f"- {s}" for s in missing_skills),
        role=role,
        candidate_name=candidate_name,
        candidate_context=candidate_context[:800],
    )
    raw = llm.invoke(prompt).content.strip()

    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        return [
            {
                "question": f"Can you describe your experience with {s}?",
                "targets_requirement": s,
                "potential_score_impact": "+3%",
                "why_important": f"{s} is a required skill for this role.",
            }
            for s in missing_skills[:3]
        ]


def assess_answer(question: str, answer: str, role: str, requirement: str) -> dict:
    """AI-evaluate a candidate's answer and return an assessment score."""
    llm = _get_llm()
    prompt = ASSESSMENT_PROMPT.format(
        question=question,
        answer=answer,
        role=role,
        requirement=requirement,
    )
    raw = llm.invoke(prompt).content.strip()

    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        return {
            "relevance": 60,
            "completeness": 60,
            "evidence_strength": 60,
            "overall_quality": 60,
            "assessment_score": 60,
            "score_impact": 2,
            "feedback": "Answer recorded.",
            "verdict": "Moderate",
        }
