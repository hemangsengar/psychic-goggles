"""Adaptive difficulty engine for the quiz system."""

import json
import logging
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models.db_models import QuizQuestion, StudentAnswer, StudentProfile

logger = logging.getLogger(__name__)

DIFFICULTY_LEVELS: List[str] = ["easy", "medium", "hard"]


class AdaptiveEngine:
    """
    Adjusts quiz difficulty based on student performance streaks.

    Rules:
      - 3 consecutive correct answers  → increase difficulty (if not already at 'hard')
      - 2 consecutive incorrect answers → decrease difficulty (if not already at 'easy')
      - Otherwise                       → maintain current difficulty
    """

    PROMOTE_AFTER = 3   # consecutive correct answers needed to go up
    DEMOTE_AFTER  = 2   # consecutive incorrect answers needed to go down

    def adjust_difficulty(self, profile: StudentProfile, is_correct: bool) -> str:
        """
        Update streak counters and return the new (or unchanged) difficulty string.
        The caller is responsible for persisting the profile.
        """
        if is_correct:
            profile.consecutive_correct  += 1
            profile.consecutive_incorrect = 0
        else:
            profile.consecutive_incorrect += 1
            profile.consecutive_correct   = 0

        current_idx = DIFFICULTY_LEVELS.index(profile.current_difficulty)

        if is_correct and profile.consecutive_correct >= self.PROMOTE_AFTER:
            new_idx = min(current_idx + 1, len(DIFFICULTY_LEVELS) - 1)
            profile.consecutive_correct = 0  # reset streak after promotion
            profile.current_difficulty = DIFFICULTY_LEVELS[new_idx]

        elif not is_correct and profile.consecutive_incorrect >= self.DEMOTE_AFTER:
            new_idx = max(current_idx - 1, 0)
            profile.consecutive_incorrect = 0  # reset streak after demotion
            profile.current_difficulty = DIFFICULTY_LEVELS[new_idx]

        return profile.current_difficulty

    def get_next_question(
        self,
        db: Session,
        student_id: str,
        topic: Optional[str] = None,
        subject: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Return the next unanswered question for the student at their current difficulty.
        Falls back to adjacent difficulty levels if no question is available.
        """
        profile = db.query(StudentProfile).filter_by(student_id=student_id).first()
        current_difficulty = profile.current_difficulty if profile else "easy"

        # IDs of questions the student has already attempted
        answered_ids = {
            row.question_id
            for row in db.query(StudentAnswer.question_id)
            .filter_by(student_id=student_id)
            .all()
        }

        current_idx = DIFFICULTY_LEVELS.index(current_difficulty)
        # Try current level first, then adjacent levels
        search_order = [current_idx]
        if current_idx > 0:
            search_order.append(current_idx - 1)
        if current_idx < len(DIFFICULTY_LEVELS) - 1:
            search_order.append(current_idx + 1)

        for idx in search_order:
            difficulty = DIFFICULTY_LEVELS[idx]
            query = db.query(QuizQuestion).filter(QuizQuestion.difficulty == difficulty)

            if answered_ids:
                query = query.filter(QuizQuestion.question_id.notin_(answered_ids))

            if topic:
                from models.db_models import ContentChunk
                query = query.join(ContentChunk, QuizQuestion.chunk_id == ContentChunk.chunk_id)
                query = query.filter(ContentChunk.topic.ilike(f"%{topic}%"))

            if subject:
                from models.db_models import ContentChunk
                if topic is None:  # avoid double-join
                    query = query.join(ContentChunk, QuizQuestion.chunk_id == ContentChunk.chunk_id)
                query = query.filter(ContentChunk.subject.ilike(f"%{subject}%"))

            question = query.first()
            if question:
                return {
                    "question_id": question.question_id,
                    "question": question.question,
                    "type": question.type,
                    "options": json.loads(question.options) if question.options else None,
                    "answer": question.answer,
                    "difficulty": question.difficulty,
                    "source_chunk_id": question.chunk_id,
                }

        return None
