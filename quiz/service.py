"""Quiz service: orchestrates generation and retrieval of quiz questions."""

import json
import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models.db_models import ContentChunk, QuizQuestion
from quiz.generator import QuizGenerator

logger = logging.getLogger(__name__)


class QuizService:
    """High-level service for generating and querying quiz questions."""

    def __init__(self, db: Session):
        self.db = db
        self._generator: Optional[QuizGenerator] = None

    @property
    def generator(self) -> QuizGenerator:
        """Lazy-init: only create the generator (and read the API key) when needed."""
        if self._generator is None:
            self._generator = QuizGenerator()
        return self._generator

    def generate_for_source(self, source_id: str, questions_per_chunk: int = 3) -> List[Dict]:
        """
        Generate quiz questions for all chunks belonging to source_id.
        Skips duplicate questions (based on exact question text match within this source).
        Returns the list of newly created question dicts.
        """
        chunks = (
            self.db.query(ContentChunk)
            .filter(ContentChunk.source_id == source_id)
            .order_by(ContentChunk.chunk_index)
            .all()
        )

        if not chunks:
            raise ValueError(f"No content chunks found for source_id '{source_id}'.")

        # Build a set of existing question texts for duplicate detection
        existing_texts = {
            q.question
            for q in self.db.query(QuizQuestion.question)
            .filter(QuizQuestion.source_id == source_id)
            .all()
        }

        created = []
        for chunk in chunks:
            chunk_dict = {
                "chunk_id": chunk.chunk_id,
                "source_id": chunk.source_id,
                "grade": chunk.grade,
                "subject": chunk.subject,
                "topic": chunk.topic,
                "text": chunk.text,
            }
            generated = self.generator.generate_questions(chunk_dict, questions_per_chunk)

            # Count existing questions for this chunk once before iterating
            base_count = (
                self.db.query(QuizQuestion)
                .filter(QuizQuestion.chunk_id == chunk.chunk_id)
                .count()
            )
            new_q_index = 0
            for q_data in generated:
                if q_data["question"] in existing_texts:
                    logger.debug("Skipping duplicate question: %s", q_data["question"][:60])
                    continue

                question_id = f"Q_{chunk.chunk_id}_{base_count + new_q_index + 1:03d}"
                new_q_index += 1

                db_question = QuizQuestion(
                    question_id=question_id,
                    chunk_id=chunk.chunk_id,
                    source_id=source_id,
                    question=q_data["question"],
                    type=q_data["type"],
                    options=json.dumps(q_data["options"]) if q_data["options"] else None,
                    answer=q_data["answer"],
                    difficulty=q_data["difficulty"],
                )
                self.db.add(db_question)
                existing_texts.add(q_data["question"])

                created.append({
                    "question_id": question_id,
                    "question": q_data["question"],
                    "type": q_data["type"],
                    "options": q_data["options"],
                    "answer": q_data["answer"],
                    "difficulty": q_data["difficulty"],
                    "source_chunk_id": chunk.chunk_id,
                })

        self.db.commit()
        return created

    def get_questions(
        self,
        topic: Optional[str] = None,
        difficulty: Optional[str] = None,
        subject: Optional[str] = None,
        grade: Optional[int] = None,
        limit: int = 10,
    ) -> List[Dict]:
        """
        Retrieve quiz questions with optional filters.
        - topic: case-insensitive substring match against ContentChunk.topic
        - difficulty: exact match ("easy", "medium", "hard")
        - subject: case-insensitive substring match against ContentChunk.subject
        - grade: exact match against ContentChunk.grade
        """
        query = self.db.query(QuizQuestion)

        # Join with ContentChunk only when topic/subject/grade filters are active
        if topic or subject or grade is not None:
            query = query.join(ContentChunk, QuizQuestion.chunk_id == ContentChunk.chunk_id)
            if topic:
                query = query.filter(ContentChunk.topic.ilike(f"%{topic}%"))
            if subject:
                query = query.filter(ContentChunk.subject.ilike(f"%{subject}%"))
            if grade is not None:
                query = query.filter(ContentChunk.grade == grade)

        if difficulty:
            query = query.filter(QuizQuestion.difficulty == difficulty.lower())

        rows = query.limit(limit).all()
        return [self._to_dict(q) for q in rows]

    @staticmethod
    def _to_dict(q: QuizQuestion) -> Dict:
        return {
            "question_id": q.question_id,
            "question": q.question,
            "type": q.type,
            "options": json.loads(q.options) if q.options else None,
            "answer": q.answer,
            "difficulty": q.difficulty,
            "source_chunk_id": q.chunk_id,
        }
