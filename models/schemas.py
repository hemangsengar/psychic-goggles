from typing import List, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    grade: int
    subject: str


class IngestResponse(BaseModel):
    source_id: str
    filename: str
    chunks_created: int
    status: str


# ---------------------------------------------------------------------------
# Content chunk
# ---------------------------------------------------------------------------

class ChunkResponse(BaseModel):
    source_id: str
    chunk_id: str
    grade: int
    subject: str
    topic: str
    text: str


# ---------------------------------------------------------------------------
# Quiz generation
# ---------------------------------------------------------------------------

class GenerateQuizRequest(BaseModel):
    source_id: str
    questions_per_chunk: int = 3


class QuizQuestionSchema(BaseModel):
    question_id: str
    question: str
    type: str                           # MCQ, TRUE_FALSE, FILL_BLANK
    options: Optional[List[str]] = None
    answer: str
    difficulty: str
    source_chunk_id: str


# ---------------------------------------------------------------------------
# Quiz retrieval
# ---------------------------------------------------------------------------

class QuizListResponse(BaseModel):
    questions: List[QuizQuestionSchema]
    total: int


# ---------------------------------------------------------------------------
# Answer submission
# ---------------------------------------------------------------------------

class SubmitAnswerRequest(BaseModel):
    student_id: str
    question_id: str
    selected_answer: str


class SubmitAnswerResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    new_difficulty: str
    message: str


# ---------------------------------------------------------------------------
# Student profile
# ---------------------------------------------------------------------------

class StudentProfileResponse(BaseModel):
    student_id: str
    current_difficulty: str
    total_correct: int
    total_answered: int
    accuracy_percentage: float


class StudentAnswerHistory(BaseModel):
    question_id: str
    question: str
    selected_answer: str
    correct_answer: str
    is_correct: bool
    difficulty_at_attempt: str
    answered_at: str
