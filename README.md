# Unified Grading System for Multiple Choice and Descriptive Answers

An AI-powered grading platform that combines automatic multiple-choice evaluation with intelligent descriptive answer grading using OCR, RAG, and LLMs.

## Features

- **Multiple-choice grading** — instant, rule-based scoring
- **Descriptive answer grading** — handwriting/answer-sheet OCR via Tesseract + optional vision LLM, followed by RAG-augmented LLM evaluation against teacher-provided materials
- **Off-topic detection** — automatically zeros answers that don't address the question
- **Automatic flagging** — submissions with low OCR confidence, low similarity, or invalid LLM responses are queued for manual review
- **Manual review dashboard** — admins can override marks and feedback on flagged results
- **Teacher materials ingestion** — upload reference documents that get chunked and embedded into ChromaDB for RAG retrieval
- **Role-based access** — student, teacher, and admin roles with JWT authentication
- **Analytics panel** — per-exam score distributions and grading statistics

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django, Django REST Framework, SimpleJWT |
| Frontend | React 19, Vite, React Router v7 |
| Database | PostgreSQL (psycopg2) |
| OCR | Tesseract (pytesseract), OpenCV, optional Ollama vision model |
| LLM | Ollama (llama3) or OpenAI API |
| Embeddings / RAG | sentence-transformers, ChromaDB, LangChain |
| Containerization | Docker (multi-stage build) |

## Project Structure

```
├── backend/
│   ├── config/              # Django settings, URLs, WSGI/ASGI
│   └── apps/
│       ├── authentication/  # Custom User model, JWT login/register
│       ├── descriptive_grading/
│       │   ├── models.py    # Exam, Question, Submission, DescriptiveResult
│       │   ├── pipeline/    # OCR → RAG → LLM grading pipeline
│       │   └── management/  # Evaluation commands
│       └── manual_review/   # Flag review queue for admins
├── frontend/
│   └── src/
│       ├── pages/           # Login, Register, role-based home pages
│       └── components/      # Dashboards, result viewer, analytics
├── Dockerfile               # Multi-stage build (Node + Python)
├── requirements.txt
└── .env.example
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL
- Tesseract OCR installed and on PATH
- (Optional) Ollama running locally for LLM grading

### 1. Clone and configure

```bash
git clone <repo-url>
cd Unified-Grading-System-for-Multiple-Choice-and-Descriptive-Answers
cp .env.example .env
```

Edit `.env` with your database credentials, LLM provider settings, and a secure `DJANGO_SECRET_KEY`.

### 2. Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r ../requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs on `http://localhost:3000` by default.

### 4. Docker (alternative)

```bash
docker build -t grading-system .
docker run -p 8000:8000 --env-file .env grading-system
```

This builds the frontend, bundles it with the backend, and serves everything via Gunicorn on port 8000.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `ollama` or `openai` | `ollama` |
| `OLLAMA_MODEL` | Ollama model name for text grading | `llama3` |
| `OLLAMA_VISION_MODEL` | Ollama model for vision OCR | `qwen2.5vl:3b` |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `SIMILARITY_THRESHOLD` | Min RAG similarity to avoid flagging | `0.45` |
| `ANSWER_RELEVANCE_THRESHOLD` | Min answer-question relevance | `0.4` |
| `OCR_CONFIDENCE_THRESHOLD` | Min OCR confidence to proceed with grading | `60` |
| `POSTGRES_DB` | Database name | `grading_db` |
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | — |
| `DJANGO_SECRET_KEY` | Django secret key | — |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins | `http://localhost:3000` |

See `.env.example` for the full list.

## How Grading Works

1. **Student submits** an answer sheet image for each question in an exam
2. **OCR extraction** — Tesseract (or vision LLM) extracts text from the image
3. **Relevance check** — the answer is compared against the question; off-topic answers get zero marks
4. **RAG retrieval** — the question is embedded and matched against teacher materials stored in ChromaDB
5. **LLM grading** — the question, rubric, retrieved context, and student answer are sent to the LLM, which returns marks, feedback, and a point-by-point justification
6. **Validation & flagging** — scores outside valid ranges, low confidence, or retrieval failures trigger automatic flagging
7. **Manual review** — flagged items appear in the admin review queue for override

## API Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/register/` | POST | Register a new user |
| `/api/auth/login/` | POST | Obtain JWT access + refresh tokens |
| `/api/auth/token/refresh/` | POST | Refresh an access token |
| `/api/exams/` | GET/POST | List or create exams (teacher) |
| `/api/submissions/` | GET/POST | List or create submissions (student) |
| `/api/materials/` | GET/POST | Upload/manage teacher reference materials |
| `/api/review/` | GET/PUT | Admin manual review queue |
