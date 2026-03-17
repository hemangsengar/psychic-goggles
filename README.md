# Peblo Quiz Engine

A backend system that ingests educational PDFs, generates quiz questions with Claude AI, and serves them through a REST API with adaptive difficulty.

---

## Repository Structure

```
peblo-backend/
├── main.py                  # FastAPI app entry point — all route definitions
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── data/                    # Provided sample PDFs for ingestion
├── samples/                 # Example outputs: chunks, questions, API responses, DB schema
├── models/
│   ├── database.py          # SQLAlchemy engine, SessionLocal, get_db()
│   ├── db_models.py         # ORM models: 5 tables with FK relationships
│   └── schemas.py           # Pydantic v2 request / response schemas
├── ingestion/
│   ├── pdf_extractor.py     # PyMuPDF text extraction
│   └── ingester.py          # Ingestion pipeline orchestrator
├── processing/
│   └── text_processor.py    # Text cleaning, chunking, topic extraction
├── quiz/
│   ├── generator.py         # Claude API prompt + response parsing
│   └── service.py           # Question generation, dedup, retrieval
└── evaluation/
    ├── adaptive.py          # Streak-based difficulty adjustment engine
    └── service.py           # Answer submission, student profile, history
```

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

### Module Breakdown

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

### 1. Clone the repository

```bash
git clone https://github.com/hemangsengar/psychic-goggles.git
cd psychic-goggles
```

### 2. Install dependencies

```bash
python3.12 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example env file and fill in your API key:

```bash
cp .env.example .env
```

Open `.env` and set:

```
LLM_API_KEY=your_anthropic_api_key_here
DATABASE_URL=sqlite:///./peblo.db
```

> `.env.example` ships with empty values — do not commit real credentials.

### 4. Run the backend

```bash
source venv/bin/activate
uvicorn main:app --reload
```

- API base URL: `http://localhost:8000`
- Interactive Swagger docs: `http://localhost:8000/docs`

The SQLite database (`peblo.db`) is created automatically on first run.

---

## Testing Endpoints

Run these curl commands in order to test the full pipeline.

### Step 1 — Health check

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status": "ok", "service": "peblo-quiz-engine"}
```

---

### Step 2 — Ingest the provided PDFs

```bash
# Grade 1 Math
curl -X POST http://localhost:8000/ingest \
  -F "file=@data/peblo_pdf_grade1_math_numbers.pdf" \
  -F "grade=1" \
  -F "subject=Math"

# Grade 3 Science
curl -X POST http://localhost:8000/ingest \
  -F "file=@data/peblo_pdf_grade3_science_plants_animals.pdf" \
  -F "grade=3" \
  -F "subject=Science"

# Grade 4 English
curl -X POST http://localhost:8000/ingest \
  -F "file=@data/peblo_pdf_grade4_english_grammar.pdf" \
  -F "grade=4" \
  -F "subject=English"
```

Expected response (each):
```json
{
  "source_id": "SRC_A1B2C3",
  "filename": "peblo_pdf_grade1_math_numbers.pdf",
  "chunks_created": 1,
  "status": "processed"
}
```

> Note the `source_id` from each response — you'll need it in the next step.

---

### Step 3 — Generate quiz questions

Replace `SRC_A1B2C3` with your actual `source_id`:

```bash
curl -X POST http://localhost:8000/generate-quiz \
  -H "Content-Type: application/json" \
  -d '{"source_id": "SRC_A1B2C3", "questions_per_chunk": 3}'
```

Expected:
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

---

### Step 4 — Retrieve quiz questions (with filters)

```bash
# All questions (default limit 10)
curl "http://localhost:8000/quiz"

# Filter by difficulty
curl "http://localhost:8000/quiz?difficulty=easy"

# Filter by subject
curl "http://localhost:8000/quiz?subject=Science"

# Filter by grade + difficulty
curl "http://localhost:8000/quiz?grade=4&difficulty=easy"

# Filter by topic
curl "http://localhost:8000/quiz?topic=shapes&limit=5"
```

---

### Step 5 — Submit answers (triggers adaptive difficulty)

Replace `question_id` with a real ID from Step 3:

```bash
# Correct answer
curl -X POST http://localhost:8000/submit-answer \
  -H "Content-Type: application/json" \
  -d '{
    "student_id": "S001",
    "question_id": "Q_SRC_A1B2C3_CH_01_001",
    "selected_answer": "3"
  }'
```

Expected:
```json
{
  "is_correct": true,
  "correct_answer": "3",
  "new_difficulty": "easy",
  "message": "Correct! Great job!"
}
```

> After **3 consecutive correct** answers `new_difficulty` promotes to `medium`.
> After **2 consecutive wrong** answers it demotes back to `easy`.

---

### Step 6 — Student profile and history

```bash
# Current difficulty level and accuracy
curl http://localhost:8000/student/S001/profile

# Answer history (newest first)
curl http://localhost:8000/student/S001/history

# Next unanswered question at current difficulty
curl http://localhost:8000/student/S001/next-question
```

---

## API Reference

### POST `/ingest`
Upload a PDF and extract/store its content.

### POST `/generate-quiz`
Generate MCQ, True/False, and Fill-in-the-blank questions from an ingested source via Claude.

### GET `/quiz`
Retrieve questions. Filters: `topic`, `difficulty`, `subject`, `grade`, `limit`.

### POST `/submit-answer`
Submit a student answer. Returns correctness and updated difficulty.

### GET `/student/{student_id}/profile`
Returns current difficulty, total answered, total correct, accuracy %.

### GET `/student/{student_id}/history`
Returns full answer history, newest first.

### GET `/student/{student_id}/next-question`
Returns the next unanswered question at the student's current difficulty.

### GET `/health`
Service health check.

> Full interactive docs with request/response schemas: `http://localhost:8000/docs`

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

## Sample Outputs

See the `samples/` directory for:

- `extracted_chunks.json` — example content chunks after ingestion
- `generated_questions.json` — example quiz questions from all 3 PDFs
- `api_responses.json` — example response for every endpoint
- `database_schema.sql` — full schema with indexes

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
