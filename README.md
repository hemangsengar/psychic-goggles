
A backend system that ingests educational PDFs, generates quiz questions with Claude AI, and serves them through a REST API with adaptive difficulty.

---

## Architecture

```
PDF Upload
    │
    ▼
POST /ingest                        ← multipart/form-data (file + grade + subject)
    │  ingestion/ingester.py
    │  ├─ PDFExtractor  (PyMuPDF)   → raw text per page
    │  └─ TextProcessor             → clean, paragraph-chunk, extract topic
    │
    ▼
SQLite (peblo.db)
    ├─ source_documents
    ├─ content_chunks
    ├─ quiz_questions
    ├─ student_answers
    └─ student_profiles
    │
    ▼
POST /generate-quiz                 ← { source_id, questions_per_chunk }
    │  quiz/service.py
    │  └─ QuizGenerator             → Anthropic claude-haiku-4-5
    │      MCQ · True/False · Fill-in-the-blank
    │      duplicate detection per source
    │
    ▼
GET  /quiz                          ← ?topic= &difficulty= &subject= &grade= &limit=
POST /submit-answer                 ← { student_id, question_id, selected_answer }
    │  evaluation/service.py
    │  └─ AdaptiveEngine            → streak-based difficulty adjustment
    │
    ▼
GET  /student/{id}/profile
GET  /student/{id}/history
GET  /student/{id}/next-question
GET  /health
```

### Module breakdown

| Module | Responsibility |
|---|---|
| `models/database.py` | SQLAlchemy engine, `SessionLocal`, `get_db()` FastAPI dependency |
| `models/db_models.py` | 5 ORM models with FK relationships |
| `models/schemas.py` | Pydantic v2 request / response schemas |
| `ingestion/` | PDF text extraction, ingestion pipeline orchestration |
| `processing/` | Text cleaning, topic heuristics, paragraph/sentence chunking |
| `quiz/` | Claude-powered generation, duplicate detection, filtered retrieval |
| `evaluation/` | Answer evaluation, adaptive difficulty, student profiling |
| `main.py` | FastAPI app + all route definitions |

### Adaptive Difficulty Algorithm

| Event | Effect |
|---|---|
| 3 consecutive correct answers | Promote: easy → medium → hard |
| 2 consecutive incorrect answers | Demote: hard → medium → easy |
| Promotion / demotion | Streak counter resets |

---

## Setup

### Prerequisites

- Python **3.12** (3.13+ not yet supported by pydantic-core)
- An [Anthropic API key](https://console.anthropic.com/)

### Install

```bash
git clone <repo-url>
cd peblo-backend

python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Configure environment

```bash
cp .env.example .env
# Open .env and paste your ANTHROPIC_API_KEY
```

`.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
DATABASE_URL=sqlite:///./peblo.db
```

### Run

```bash
source venv/bin/activate
uvicorn main:app --reload
```

- API base: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`

---

## API Reference

### POST `/ingest`

Upload a PDF and extract/store its content.

```bash
curl -X POST http://localhost:8000/ingest \
  -F "file=@peblo_pdf_grade1_math_numbers.pdf" \
  -F "grade=1" \
  -F "subject=Math"
```

```json
{
  "source_id": "SRC_A1B2C3",
  "filename": "peblo_pdf_grade1_math_numbers.pdf",
  "chunks_created": 8,
  "status": "processed"
}
```

---

### POST `/generate-quiz`

Generate questions from an ingested source using Claude.

```bash
curl -X POST http://localhost:8000/generate-quiz \
  -H "Content-Type: application/json" \
  -d '{"source_id": "SRC_A1B2C3", "questions_per_chunk": 3}'
```

```json
[
  {
    "question_id": "Q_SRC_A1B2C3_CH_01_001",
    "question": "How many sides does a triangle have?",
    "type": "MCQ",
    "options": ["2", "3", "4", "5"],
    "answer": "3",
    "difficulty": "easy",
    "source_chunk_id": "SRC_A1B2C3_CH_01"
  }
]
```

Question types: `MCQ` · `TRUE_FALSE` · `FILL_BLANK`
Difficulty: `easy` · `medium` · `hard` (grade-aware)

---

### GET `/quiz`

Retrieve questions with optional filters.

| Query param | Type | Description |
|---|---|---|
| `topic` | string | Partial match on chunk topic |
| `difficulty` | string | `easy` / `medium` / `hard` |
| `subject` | string | Partial match on subject |
| `grade` | int | Exact grade level |
| `limit` | int | Max results (1–100, default 10) |

```bash
curl "http://localhost:8000/quiz?topic=shapes&difficulty=easy&limit=5"
curl "http://localhost:8000/quiz?grade=3&subject=Science"
```

```json
{
  "questions": [ ... ],
  "total": 5
}
```

---

### POST `/submit-answer`

Submit a student's answer; triggers adaptive difficulty update.

```bash
curl -X POST http://localhost:8000/submit-answer \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "S001",
    "question_id": "Q_SRC_A1B2C3_CH_01_001",
    "selected_answer": "3"
  }'
```

```json
{
  "is_correct": true,
  "correct_answer": "3",
  "new_difficulty": "easy",
  "message": "Correct! Great job!"
}
```

---

### GET `/student/{student_id}/profile`

```bash
curl http://localhost:8000/student/S001/profile
```

```json
{
  "student_id": "S001",
  "current_difficulty": "medium",
  "total_correct": 7,
  "total_answered": 10,
  "accuracy_percentage": 70.0
}
```

---

### GET `/student/{student_id}/history?limit=20`

Returns the student's answer history, newest first.

---

### GET `/student/{student_id}/next-question`

Returns the next unanswered question at the student's current difficulty.
Falls back to adjacent difficulty levels if exhausted.

| Query param | Description |
|---|---|
| `topic` | Optional topic filter |
| `subject` | Optional subject filter |

---

### GET `/health`

```json
{ "status": "ok", "service": "peblo-quiz-engine" }
```

---

## Database Schema

```
source_documents
  source_id (PK), filename, grade, subject, file_path, status, created_at

content_chunks
  chunk_id (PK), source_id (FK), grade, subject, topic, text, chunk_index, created_at

quiz_questions
  question_id (PK), chunk_id (FK), source_id, question, type, options (JSON),
  answer, difficulty, created_at

student_answers
  id (PK), student_id, question_id (FK), selected_answer, is_correct,
  difficulty_at_attempt, created_at

student_profiles
  student_id (PK), current_difficulty, consecutive_correct, consecutive_incorrect,
  total_correct, total_answered, updated_at
```

All quiz questions carry a `source_chunk_id` — full traceability from question → chunk → source PDF.

---

## Sample Data

**Content chunk (stored after ingestion):**
```json
{
  "source_id": "SRC_A1B2C3",
  "chunk_id": "SRC_A1B2C3_CH_01",
  "grade": 1,
  "subject": "Math",
  "topic": "Counting Numbers",
  "text": "Numbers help us count objects. We start counting from 1..."
}
```

**Generated question:**
```json
{
  "question_id": "Q_SRC_A1B2C3_CH_01_001",
  "question": "What number do we start counting from?",
  "type": "MCQ",
  "options": ["0", "1", "2", "10"],
  "answer": "1",
  "difficulty": "easy",
  "source_chunk_id": "SRC_A1B2C3_CH_01"
}
```

---

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI |
| Database | SQLite via SQLAlchemy ORM |
| LLM | Anthropic Claude (`claude-haiku-4-5-20251001`) |
| PDF parsing | PyMuPDF (`fitz`) |
| Validation | Pydantic v2 |
| Server | Uvicorn |
