# 🎯 AI Recruiter Copilot

> Reuse existing candidates before sourcing externally.

**Stack:** LangChain · Groq Llama 3 70B · FAISS · SQLite · HuggingFace Embeddings · Gradio

---

## Project Structure

```
ai_recruiter_copilot/
├── modules/
│   ├── database.py          # SQLite schema + all CRUD helpers
│   ├── data_generator.py    # Generate 500 realistic candidates
│   ├── faiss_builder.py     # Build & query FAISS vector index
│   ├── jd_intelligence.py   # JD parsing via Groq LLM
│   ├── structured_search.py # SQL-based structured search
│   ├── semantic_search.py   # FAISS semantic search
│   ├── hybrid_search.py     # Merge SQL + FAISS + Score + Rank
│   ├── scoring.py           # Match / Confidence / Engagement scores
│   ├── rag_engine.py        # RAG match details (RetrievalQA)
│   ├── question_generator.py# AI question gen + answer assessment
│   ├── reranker.py          # Dynamic re-ranking per job
│   ├── workflow.py          # Recruiter workflow tracker
│   ├── submission.py        # One-click PDF report generation
│   └── feedback.py          # Feedback loop + analytics charts
├── data/                    # SQLite DB (auto-created)
├── faiss_index/             # FAISS index files (auto-created)
├── exports/                 # PDF reports (auto-created)
├── gradio_app.py            # Main Gradio UI (8 screens)
├── AI_Recruiter_Copilot.ipynb  # Step-by-step Jupyter notebook
├── requirements.txt
├── .env.example
└── README.md
```

---

## Setup Guide

### 1. Clone / Copy Project

```bash
cd C:\
```

### 2. Create Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `torch` may take several minutes. If you hit issues, install CPU-only:
> ```bash
> pip install torch --index-url https://download.pytorch.org/whl/cpu
> ```

### 4. Configure API Key

```bash
copy .env.example .env
```

Edit `.env`:
```env
GROQ_API_KEY=gsk_your_key_here
```

Get a free Groq API key at: https://console.groq.com

### 5. Run via Jupyter Notebook

```bash
jupyter notebook AI_Recruiter_Copilot.ipynb
```

Run cells top-to-bottom. First run:
- Seeds 500 candidates into SQLite
- Builds FAISS index (~2-3 min)
- Launches Gradio at http://localhost:7860

### 6. OR Run Gradio Directly

```bash
python gradio_app.py
```

Then click **🚀 Initialize System** in the UI.

---

## Features

| # | Feature | Module |
|---|---------|--------|
| 1 | JD Upload (text/PDF/voice) | `jd_intelligence.py` |
| 2 | JD Intelligence Engine | `jd_intelligence.py` |
| 3 | 500-candidate sample database | `data_generator.py` |
| 4 | Text-to-SQL Engine | `structured_search.py` |
| 5 | Semantic Search (FAISS) | `semantic_search.py` |
| 6 | Hybrid Search | `hybrid_search.py` |
| 7 | Match Scoring | `scoring.py` |
| 8 | Confidence Score | `scoring.py` |
| 9 | Engagement Score | `scoring.py` |
| 10 | Final Ranking | `hybrid_search.py` |
| 11 | RAG Match Details | `rag_engine.py` |
| 12 | Gap Detection | `rag_engine.py` |
| 13 | AI Question Generation | `question_generator.py` |
| 14 | Candidate Assessment | `question_generator.py` |
| 15 | Dynamic Re-Ranking | `reranker.py` |
| 16 | Workflow Tracker | `workflow.py` |
| 17 | Recruiter Memory | `database.py` |
| 18 | One-Click Submission (PDF) | `submission.py` |
| 19 | Feedback Loop + Analytics | `feedback.py` |

---

## Scoring Formula

```
Match Score    = 70% Structured + 30% Semantic
                 (Structured = Skills 35% + Exp 25% + Location 15% + Industry 15% + CTC 10%)

Final Score    = 60% Match Score + 20% Confidence Score + 20% Engagement Score

Updated Score  = Final Score ± Assessment Score Impact (per-job only)
```

---

## Gradio Screens

| Screen | Tab |
|--------|-----|
| JD Upload | Tab 1 |
| Candidate Search Results | Tab 2 |
| Ranking Table | Tab 2 |
| Match Details (RAG) | Tab 3 |
| Assessment Panel | Tab 4 |
| Workflow Tracker | Tab 5 |
| Recruiter Notes | Tab 6 |
| Submission Report | Tab 7 |
| Analytics Dashboard | Tab 8 |

---

## SQLite Schema

| Table | Purpose |
|-------|---------|
| `candidates` | 500 candidate profiles |
| `engagement_data` | Response rate, interview attendance |
| `jobs` | Parsed JD store |
| `job_candidates` | Per-job scores and status |
| `recruiter_memory` | Q&A history and notes |
| `workflow_history` | Status change log |
| `job_assessments` | Dynamic re-ranking data |
| `feedback` | Hiring outcomes |

---

## Troubleshooting

**FAISS import error on Windows:**
```bash
pip install faiss-cpu --no-cache-dir
```

**Groq rate limit:** The free tier allows 30 req/min on Llama 3 70B. Add `time.sleep(2)` between LLM calls if needed.

**SpeechRecognition / PyAudio:** Voice input requires `pyaudio`. On Windows:
```bash
pip install pipwin
pipwin install pyaudio
```

**torch slow install:** Use CPU-only wheel (see Step 3 above).
