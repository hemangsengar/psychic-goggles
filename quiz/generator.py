"""Quiz question generation using the Anthropic Claude API."""

import json
import logging
import os
import re
from typing import Dict, List, Optional

import anthropic

logger = logging.getLogger(__name__)


class QuizGenerator:
    """Generates quiz questions from educational content chunks via Claude."""

    DIFFICULTY_BY_GRADE = {
        1: ["easy"],
        2: ["easy"],
        3: ["easy", "medium"],
        4: ["easy", "medium"],
        5: ["medium", "hard"],
        6: ["medium", "hard"],
    }

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY (or LLM_API_KEY) environment variable is not set.")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-haiku-4-5-20251001"

    def generate_questions(self, chunk: Dict, questions_per_chunk: int = 3) -> List[Dict]:
        """
        Generate quiz questions for a single content chunk.

        Args:
            chunk: dict with keys chunk_id, source_id, grade, subject, topic, text
            questions_per_chunk: how many questions to generate

        Returns:
            List of question dicts with source_chunk_id injected.
        """
        grade = chunk.get("grade", 3)
        difficulties = self.DIFFICULTY_BY_GRADE.get(grade, ["easy", "medium"])

        prompt = self._build_prompt(chunk, questions_per_chunk, difficulties)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = message.content[0].text
            questions = self._parse_llm_response(response_text, chunk["chunk_id"])
            return questions
        except anthropic.APIError as e:
            logger.error("Anthropic API error for chunk %s: %s", chunk.get("chunk_id"), e)
            return []
        except Exception as e:
            logger.error("Unexpected error generating questions for chunk %s: %s", chunk.get("chunk_id"), e)
            return []

    def _build_prompt(self, chunk: Dict, n: int, difficulties: List[str]) -> str:
        grade = chunk.get("grade", 3)
        subject = chunk.get("subject", "General")
        topic = chunk.get("topic", "General")
        text = chunk.get("text", "")
        difficulty_str = " and ".join(difficulties)

        return f"""You are an educational quiz generator for grade {grade} students studying {subject}.

Based on the following educational content, generate exactly {n} quiz questions.

Content topic: {topic}
Content:
{text}

Generate a mix of question types:
- MCQ (multiple choice with 4 options)
- TRUE_FALSE (answer is "True" or "False")
- FILL_BLANK (sentence with a blank, answer fills the blank)

Difficulty should be {difficulty_str} — appropriate for grade {grade}.

Return ONLY a valid JSON array with this exact structure (no markdown, no extra text):
[
  {{
    "question": "How many sides does a triangle have?",
    "type": "MCQ",
    "options": ["2", "3", "4", "5"],
    "answer": "3",
    "difficulty": "easy"
  }},
  {{
    "question": "Plants make their own food through ___.",
    "type": "FILL_BLANK",
    "options": null,
    "answer": "photosynthesis",
    "difficulty": "easy"
  }},
  {{
    "question": "The sun is a star.",
    "type": "TRUE_FALSE",
    "options": ["True", "False"],
    "answer": "True",
    "difficulty": "easy"
  }}
]

Rules:
- For MCQ: options must be a list of exactly 4 strings; answer must be one of those strings.
- For TRUE_FALSE: options must be ["True", "False"]; answer must be "True" or "False".
- For FILL_BLANK: options must be null; answer is the word/phrase that fills the blank.
- Questions must be based ONLY on the provided content.
- No duplicate questions.
- Return exactly {n} questions."""

    def _parse_llm_response(self, response_text: str, chunk_id: str) -> List[Dict]:
        """Extract and validate the JSON array from the LLM response."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", response_text).strip()
        cleaned = cleaned.rstrip("`").strip()

        # Find the JSON array boundaries
        start = cleaned.find("[")
        end = cleaned.rfind("]") + 1
        if start == -1 or end == 0:
            logger.warning("No JSON array found in LLM response for chunk %s", chunk_id)
            return []

        try:
            questions = json.loads(cleaned[start:end])
        except json.JSONDecodeError as e:
            logger.error("JSON parse error for chunk %s: %s", chunk_id, e)
            return []

        validated = []
        for q in questions:
            if not isinstance(q, dict):
                continue
            if not all(k in q for k in ("question", "type", "answer", "difficulty")):
                continue
            q_type = q.get("type", "").upper()
            if q_type not in ("MCQ", "TRUE_FALSE", "FILL_BLANK"):
                continue
            validated.append({
                "question": str(q["question"]),
                "type": q_type,
                "options": q.get("options"),
                "answer": str(q["answer"]),
                "difficulty": str(q.get("difficulty", "easy")),
                "source_chunk_id": chunk_id,
            })

        return validated
