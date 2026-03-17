"""
Peblo AI Backend — Content Ingestion + Adaptive Quiz Engine
FastAPI application entry point.
"""

import logging
import os
import shutil
import tempfile
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

load_dotenv()  # load .env before any module reads os.getenv()

from models.database import engine, get_db
from models import Base
from models.schemas import (
    GenerateQuizRequest,
    IngestResponse,
    QuizListResponse,
    QuizQuestionSchema,
    StudentAnswerHistory,
    StudentProfileResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from ingestion.ingester import PDFIngester
from quiz.service import QuizService
from evaluation.service import EvaluationService

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Peblo Quiz Engine",
    description="Content ingestion and adaptive quiz generation API",
    version="1.0.0",
)

# Create all DB tables on startup
Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# 1. Content Ingestion
# ---------------------------------------------------------------------------

@app.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest_pdf(
    file: UploadFile = File(..., description="PDF file to ingest"),
    grade: int = Form(..., description="Grade level (e.g. 1, 3, 4)"),
    subject: str = Form(..., description="Subject (e.g. Math, Science, English)"),
    db: Session = Depends(get_db),
):
    """
    Upload a PDF, extract its text, chunk it, and store in the database.
    Returns a source_id you can use to generate quiz questions.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Save upload to a temp file (UploadFile is a stream)
    suffix = os.path.splitext(file.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        ingester = PDFIngester(db)
        result = ingester.ingest(tmp_path, grade=grade, subject=subject, original_filename=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Ingestion failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
    finally:
        os.unlink(tmp_path)

    return result


# ---------------------------------------------------------------------------
# 2. Quiz Generation
# ---------------------------------------------------------------------------

@app.post("/generate-quiz", response_model=List[QuizQuestionSchema], tags=["Quiz"])
def generate_quiz(
    body: GenerateQuizRequest,
    db: Session = Depends(get_db),
):
    """
    Generate quiz questions from all chunks of an already-ingested source document.
    Set questions_per_chunk to control how many questions are created per chunk (default 3).
    """
    service = QuizService(db)
    try:
        questions = service.generate_for_source(
            source_id=body.source_id,
            questions_per_chunk=body.questions_per_chunk,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Quiz generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Quiz generation failed: {e}")

    return questions


# ---------------------------------------------------------------------------
# 3. Quiz Retrieval
# ---------------------------------------------------------------------------

@app.get("/quiz", response_model=QuizListResponse, tags=["Quiz"])
def get_quiz(
    topic: Optional[str] = Query(None, description="Filter by topic (partial match)"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty: easy | medium | hard"),
    subject: Optional[str] = Query(None, description="Filter by subject (partial match)"),
    grade: Optional[int] = Query(None, description="Filter by grade level"),
    limit: int = Query(10, ge=1, le=100, description="Max number of questions to return"),
    db: Session = Depends(get_db),
):
    """
    Retrieve quiz questions with optional filters.
    Example: GET /quiz?topic=shapes&difficulty=easy&limit=5
    """
    service = QuizService(db)
    questions = service.get_questions(
        topic=topic,
        difficulty=difficulty,
        subject=subject,
        grade=grade,
        limit=limit,
    )
    return {"questions": questions, "total": len(questions)}


# ---------------------------------------------------------------------------
# 4. Answer Submission
# ---------------------------------------------------------------------------

@app.post("/submit-answer", response_model=SubmitAnswerResponse, tags=["Student"])
def submit_answer(
    body: SubmitAnswerRequest,
    db: Session = Depends(get_db),
):
    """
    Submit a student's answer to a quiz question.
    Returns whether the answer was correct and the student's updated difficulty level.
    """
    service = EvaluationService(db)
    try:
        result = service.submit_answer(
            student_id=body.student_id,
            question_id=body.question_id,
            selected_answer=body.selected_answer,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Answer submission failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Submission failed: {e}")

    return result


# ---------------------------------------------------------------------------
# 5. Student Profile & History
# ---------------------------------------------------------------------------

@app.get("/student/{student_id}/profile", response_model=StudentProfileResponse, tags=["Student"])
def get_student_profile(student_id: str, db: Session = Depends(get_db)):
    """Get a student's current difficulty level, score stats, and accuracy."""
    service = EvaluationService(db)
    return service.get_student_profile(student_id)


@app.get("/student/{student_id}/history", response_model=List[StudentAnswerHistory], tags=["Student"])
def get_student_history(
    student_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Get a student's recent answer history (newest first)."""
    service = EvaluationService(db)
    return service.get_student_history(student_id, limit=limit)


# ---------------------------------------------------------------------------
# 6. Next adaptive question
# ---------------------------------------------------------------------------

@app.get("/student/{student_id}/next-question", response_model=Optional[QuizQuestionSchema], tags=["Student"])
def get_next_question(
    student_id: str,
    topic: Optional[str] = Query(None),
    subject: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return the next unanswered question at the student's current difficulty.
    Falls back to adjacent difficulty levels if none is available.
    """
    from evaluation.adaptive import AdaptiveEngine
    question = AdaptiveEngine().get_next_question(db, student_id, topic=topic, subject=subject)
    return question


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "service": "peblo-quiz-engine"}
