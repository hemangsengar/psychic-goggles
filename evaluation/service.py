"""High-level evaluation service: answer submission, profiling, history."""

import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models.db_models import QuizQuestion, StudentAnswer, StudentProfile
from evaluation.adaptive import AdaptiveEngine

logger = logging.getLogger(__name__)


class EvaluationService:
    """Handles student answer submission and adaptive difficulty logic."""

    def __init__(self, db: Session):
        self.db = db
        self.adaptive = AdaptiveEngine()

    # ------------------------------------------------------------------
    # Answer submission
    # ------------------------------------------------------------------

    def submit_answer(self, student_id: str, question_id: str, selected_answer: str) -> Dict:
        """
        Evaluate a student's answer, update profile, and return feedback.

        Returns:
            dict with is_correct, correct_answer, new_difficulty, message
        """
        question = (
            self.db.query(QuizQuestion)
            .filter_by(question_id=question_id)
            .first()
        )
        if not question:
            raise ValueError(f"Question '{question_id}' not found.")

        is_correct = self._check_answer(selected_answer, question.answer, question.type)

        # Get or create student profile
        profile = self._get_or_create_profile(student_id)
        difficulty_at_attempt = profile.current_difficulty

        # Persist the student's answer
        answer_record = StudentAnswer(
            student_id=student_id,
            question_id=question_id,
            selected_answer=selected_answer,
            is_correct=is_correct,
            difficulty_at_attempt=difficulty_at_attempt,
        )
        self.db.add(answer_record)

        # Update profile stats
        profile.total_answered += 1
        if is_correct:
            profile.total_correct += 1
        profile.updated_at = datetime.now(timezone.utc)

        # Adapt difficulty
        new_difficulty = self.adaptive.adjust_difficulty(profile, is_correct)

        self.db.commit()

        message = (
            "Correct! Great job!" if is_correct
            else f"Incorrect. The correct answer is: {question.answer}"
        )

        return {
            "is_correct": is_correct,
            "correct_answer": question.answer,
            "new_difficulty": new_difficulty,
            "message": message,
        }

    # ------------------------------------------------------------------
    # Student profile
    # ------------------------------------------------------------------

    def get_student_profile(self, student_id: str) -> Dict:
        """Return the student's profile with computed accuracy percentage."""
        profile = self._get_or_create_profile(student_id)
        self.db.flush()  # persist new profile without committing a read-only fetch

        accuracy = (
            round(profile.total_correct / profile.total_answered * 100, 1)
            if profile.total_answered > 0
            else 0.0
        )
        return {
            "student_id": profile.student_id,
            "current_difficulty": profile.current_difficulty,
            "total_correct": profile.total_correct,
            "total_answered": profile.total_answered,
            "accuracy_percentage": accuracy,
        }

    # ------------------------------------------------------------------
    # Answer history
    # ------------------------------------------------------------------

    def get_student_history(self, student_id: str, limit: int = 20) -> List[Dict]:
        """Return paginated answer history for a student, newest first."""
        rows = (
            self.db.query(StudentAnswer, QuizQuestion)
            .join(QuizQuestion, StudentAnswer.question_id == QuizQuestion.question_id)
            .filter(StudentAnswer.student_id == student_id)
            .order_by(StudentAnswer.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "question_id": answer.question_id,
                "question": question.question,
                "selected_answer": answer.selected_answer,
                "correct_answer": question.answer,
                "is_correct": answer.is_correct,
                "difficulty_at_attempt": answer.difficulty_at_attempt,
                "answered_at": answer.created_at.isoformat(),
            }
            for answer, question in rows
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_or_create_profile(self, student_id: str) -> StudentProfile:
        profile = self.db.query(StudentProfile).filter_by(student_id=student_id).first()
        if not profile:
            profile = StudentProfile(student_id=student_id)
            self.db.add(profile)
            self.db.flush()  # assign id without committing
        return profile

    @staticmethod
    def _check_answer(selected: str, correct: str, question_type: str) -> bool:
        """Normalize and compare answers."""
        s = selected.strip().lower()
        c = correct.strip().lower()

        if question_type == "TRUE_FALSE":
            # Accept "true"/"false" or "yes"/"no" variants
            mapping = {"yes": "true", "no": "false", "1": "true", "0": "false"}
            s = mapping.get(s, s)
            c = mapping.get(c, c)

        return s == c
