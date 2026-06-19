"""JD Intelligence Engine – extracts structured signals from a job description."""

import os
import json
import uuid
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

GROQ_MODEL_FALLBACKS = [
    "llama-3.3-70b-versatile", "llama-3.1-70b-versatile",
    "llama3-8b-8192", "gemma2-9b-it",
]
GROQ_MODEL = os.getenv("GROQ_MODEL", GROQ_MODEL_FALLBACKS[0])

_llm = None

JD_EXTRACTION_PROMPT = PromptTemplate(
    input_variables=["jd_text"],
    template="""You are an expert recruiter AI. Extract structured information from the job description below.

Return a valid JSON object with these exact keys:
{{
  "role": "Job title",
  "experience_min": <number in years or 0>,
  "experience_max": <number in years or 0>,
  "skills": ["skill1", "skill2", ...],
  "industry": "Industry name",
  "location": "City or Remote",
  "responsibilities": ["responsibility1", ...],
  "compensation_min": <number in LPA or 0>,
  "compensation_max": <number in LPA or 0>,
  "education": "Education requirement or empty string",
  "nice_to_have": ["optional skill1", ...]
}}

Return ONLY the JSON. No explanation. No markdown code blocks.

Job Description:
{jd_text}
""",
)


def get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set in environment")
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
        if _llm is None:
            raise RuntimeError("All Groq models failed")
    return _llm


def extract_jd(jd_text: str) -> dict:
    """Parse raw JD text and return structured JSON."""
    llm = get_llm()
    prompt = JD_EXTRACTION_PROMPT.format(jd_text=jd_text)
    raw = llm.invoke(prompt).content.strip()

    # Strip accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: return a minimal structure
        result = {
            "role": "Unknown",
            "experience_min": 0,
            "experience_max": 0,
            "skills": [],
            "industry": "",
            "location": "",
            "responsibilities": [],
            "compensation_min": 0,
            "compensation_max": 0,
            "education": "",
            "nice_to_have": [],
        }

    result.setdefault("job_id", str(uuid.uuid4())[:8])
    return result


def parse_pdf_jd(file_path: str) -> str:
    """Extract text from a PDF job description."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        return f"Error reading PDF: {e}"


def transcribe_voice(audio_path: str) -> str:
    """Convert voice recording to text using SpeechRecognition."""
    try:
        import speech_recognition as sr
        r = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = r.record(source)
        return r.recognize_google(audio)
    except Exception as e:
        return f"Voice transcription failed: {e}"


def format_jd_display(structured: dict) -> str:
    """Format structured JD for display in UI."""
    lines = [
        f"**Role:** {structured.get('role', 'N/A')}",
        f"**Experience:** {structured.get('experience_min', 0)}–{structured.get('experience_max', 0)} years",
        f"**Skills:** {', '.join(structured.get('skills', []))}",
        f"**Industry:** {structured.get('industry', 'N/A')}",
        f"**Location:** {structured.get('location', 'N/A')}",
    ]
    if structured.get("compensation_max"):
        lines.append(
            f"**Compensation:** ₹{structured.get('compensation_min', 0)}–"
            f"{structured.get('compensation_max', 0)} LPA"
        )
    if structured.get("responsibilities"):
        lines.append("**Responsibilities:**")
        for r in structured["responsibilities"][:5]:
            lines.append(f"  • {r}")
    if structured.get("nice_to_have"):
        lines.append(f"**Nice-to-have:** {', '.join(structured['nice_to_have'])}")
    return "\n".join(lines)
