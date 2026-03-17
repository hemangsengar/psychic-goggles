from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.orm import relationship
from models.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String, unique=True, nullable=False, index=True)
    filename = Column(String, nullable=False)
    grade = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    chunks = relationship("ContentChunk", back_populates="source_document", cascade="all, delete-orphan")


class ContentChunk(Base):
    __tablename__ = "content_chunks"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(String, unique=True, nullable=False, index=True)
    source_id = Column(String, ForeignKey("source_documents.source_id"), nullable=False)
    grade = Column(Integer, nullable=False)
    subject = Column(String, nullable=False)
    topic = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    source_document = relationship("SourceDocument", back_populates="chunks")
    questions = relationship("QuizQuestion", back_populates="chunk", cascade="all, delete-orphan")


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(String, unique=True, nullable=False, index=True)
    chunk_id = Column(String, ForeignKey("content_chunks.chunk_id"), nullable=False)
    source_id = Column(String, nullable=False)
    question = Column(Text, nullable=False)
    type = Column(String, nullable=False)       # "MCQ", "TRUE_FALSE", "FILL_BLANK"
    options = Column(Text, nullable=True)       # JSON string, only for MCQ/TRUE_FALSE
    answer = Column(String, nullable=False)
    difficulty = Column(String, nullable=False) # "easy", "medium", "hard"
    created_at = Column(DateTime, default=_now, nullable=False)

    chunk = relationship("ContentChunk", back_populates="questions")
    student_answers = relationship("StudentAnswer", back_populates="question", cascade="all, delete-orphan")


class StudentAnswer(Base):
    __tablename__ = "student_answers"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, nullable=False, index=True)
    question_id = Column(String, ForeignKey("quiz_questions.question_id"), nullable=False)
    selected_answer = Column(String, nullable=False)
    is_correct = Column(Boolean, nullable=False)
    difficulty_at_attempt = Column(String, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    question = relationship("QuizQuestion", back_populates="student_answers")


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(String, unique=True, nullable=False, index=True)
    current_difficulty = Column(String, default="easy", nullable=False)
    consecutive_correct = Column(Integer, default=0, nullable=False)
    consecutive_incorrect = Column(Integer, default=0, nullable=False)
    total_correct = Column(Integer, default=0, nullable=False)
    total_answered = Column(Integer, default=0, nullable=False)
    updated_at = Column(DateTime, default=_now, onupdate=_now, nullable=False)
