"""RAG-based Match Details Engine using LangChain RetrievalQA + FAISS."""

import os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from modules.semantic_search import get_rag_context

GROQ_MODEL_FALLBACKS = [
    "llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
    "llama3-8b-8192", "gemma2-9b-it",
]
GROQ_MODEL = os.getenv("GROQ_MODEL", GROQ_MODEL_FALLBACKS[0])
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", "faiss_index")

_llm = None
_hf_embeddings = None

MATCH_DETAILS_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""You are an expert recruiter AI assistant. Using ONLY the candidate profile information provided below, answer the recruiter's question.

DO NOT hallucinate or infer information not present in the context.
If information is not available in the context, explicitly state: "Not found in profile."

Candidate Profile Context:
{context}

Recruiter Question:
{question}

Provide a structured, evidence-based answer:
""",
)

GAP_PROMPT = PromptTemplate(
    input_variables=["context", "jd_requirements"],
    template="""You are an expert recruiter AI. Analyze the candidate profile and identify gaps against the job requirements.

Candidate Profile:
{context}

Job Requirements:
{jd_requirements}

Return a JSON object with:
{{
  "matched": [
    {{"requirement": "...", "evidence": "...", "strength": "Strong/Moderate/Weak"}}
  ],
  "missing": [
    {{"requirement": "...", "note": "...", "impact": "High/Medium/Low"}}
  ],
  "overall_gap_summary": "...",
  "match_percentage": <0-100>
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
                candidate = ChatGroq(model=model, temperature=0, api_key=api_key)
                candidate.invoke("hi")
                _llm = candidate
                break
            except Exception as e:
                if "decommissioned" in str(e).lower() or "400" in str(e):
                    continue
                raise
    return _llm


def get_match_details(candidate_id: str, structured_jd: dict, candidate: dict) -> dict:
    """
    Use RAG to produce a detailed match explanation for a candidate vs JD.
    Returns structured match evidence using only retrieved chunks.
    """
    import json

    jd_requirements = "\n".join([
        f"- Role: {structured_jd.get('role', '')}",
        f"- Experience: {structured_jd.get('experience_min', 0)}-{structured_jd.get('experience_max', 0)} years",
        f"- Skills: {', '.join(structured_jd.get('skills', []))}",
        f"- Industry: {structured_jd.get('industry', '')}",
        f"- Location: {structured_jd.get('location', '')}",
    ] + [f"- {r}" for r in structured_jd.get("responsibilities", [])[:5]])

    query = f"{structured_jd.get('role', '')} {' '.join(structured_jd.get('skills', []))}"
    chunks = get_rag_context(candidate_id, query, top_n=6)
    context = "\n\n".join(chunks) if chunks else _build_profile_context(candidate)

    llm = _get_llm()

    # Gap analysis
    gap_chain_input = GAP_PROMPT.format(
        context=context,
        jd_requirements=jd_requirements,
    )
    raw_gap = llm.invoke(gap_chain_input).content.strip()

    # Strip markdown fences if present
    if "```" in raw_gap:
        raw_gap = raw_gap.split("```")[1]
        if raw_gap.startswith("json"):
            raw_gap = raw_gap[4:]
    raw_gap = raw_gap.strip()

    try:
        gap_result = json.loads(raw_gap)
    except Exception:
        gap_result = {
            "matched": [],
            "missing": [],
            "overall_gap_summary": "Unable to parse gap analysis.",
            "match_percentage": 0,
        }

    # Free-form match summary
    qa_input = MATCH_DETAILS_PROMPT.format(
        context=context,
        question=f"How well does this candidate match the requirements for a {structured_jd.get('role', 'role')}? "
                 f"Focus on: {', '.join(structured_jd.get('skills', [])[:5])}",
    )
    summary = llm.invoke(qa_input).content.strip()

    return {
        "candidate_id": candidate_id,
        "gap_analysis": gap_result,
        "match_summary": summary,
        "context_chunks": chunks[:4],
    }


def _build_profile_context(candidate: dict) -> str:
    """Build text context from a candidate dict when FAISS chunks are unavailable."""
    lines = [
        f"Name: {candidate.get('name', '')}",
        f"Experience: {candidate.get('experience_years', 0)} years",
        f"Skills: {', '.join(candidate.get('skills', []))}",
        f"Industry: {candidate.get('industry', '')}",
        f"About: {candidate.get('about_section', '')}",
    ]
    for p in candidate.get("projects", [])[:3]:
        lines.append(f"Project – {p['title']}: {p['description']}")
    for w in candidate.get("work_experience", [])[:3]:
        lines.append(f"Work – {w['title']} at {w['company']} ({w['tenure_years']} years)")
    return "\n".join(lines)


def answer_recruiter_question(candidate_id: str, candidate: dict,
                               structured_jd: dict, question: str) -> str:
    """Answer an ad-hoc recruiter question about a candidate using RAG."""
    chunks = get_rag_context(candidate_id, question, top_n=5)
    context = "\n\n".join(chunks) if chunks else _build_profile_context(candidate)
    llm = _get_llm()
    prompt = MATCH_DETAILS_PROMPT.format(context=context, question=question)
    return llm.invoke(prompt).content.strip()
