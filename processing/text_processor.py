"""Text cleaning and chunking for educational content."""

import re
from typing import List, Dict


class TextProcessor:
    """Cleans raw PDF text and splits it into meaningful chunks."""

    def clean_text(self, text: str) -> str:
        """Remove noise: non-printable chars, excessive whitespace, normalize newlines."""
        # Remove non-printable characters (keep newlines and tabs)
        text = re.sub(r"[^\x09\x0A\x0D\x20-\x7E\u00A0-\uFFFF]", "", text)
        # Collapse 3+ consecutive newlines into 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Collapse multiple spaces/tabs into a single space
        text = re.sub(r"[ \t]+", " ", text)
        # Strip leading/trailing whitespace from each line
        lines = [line.strip() for line in text.splitlines()]
        text = "\n".join(lines)
        return text.strip()

    def extract_topic(self, text: str) -> str:
        """Heuristically find the heading/topic of a text chunk."""
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[:5]:  # Look only in the first 5 non-empty lines
            # Heading: short line (< 60 chars) that doesn't end with a period
            if len(line) < 60 and not line.endswith(".") and len(line) > 3:
                # Clean up numbering like "1.", "1)", "Chapter 1 -"
                topic = re.sub(r"^[\d]+[.)]\s*", "", line)
                topic = re.sub(r"^(chapter|section|unit|lesson)\s+[\d]+\s*[-:]\s*", "", topic, flags=re.IGNORECASE)
                return topic.strip() or "General"
        return "General"

    def chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks of approximately chunk_size characters.
        Prefers paragraph boundaries, falls back to sentence boundaries.
        """
        # Split on paragraph breaks first
        paragraphs = re.split(r"\n\n+", text)
        chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph keeps us under the limit, append it
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk = (current_chunk + "\n\n" + para).strip()
            else:
                # Save current chunk if it has content
                if current_chunk:
                    chunks.append(current_chunk)

                # If the paragraph itself is too large, split by sentence
                if len(para) > chunk_size:
                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    current_chunk = ""
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                            current_chunk = (current_chunk + " " + sentence).strip()
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            current_chunk = sentence
                else:
                    # Start a new chunk, optionally carrying over overlap from previous
                    overlap_text = current_chunk[-overlap:] if chunks and overlap else ""
                    current_chunk = (overlap_text + "\n\n" + para).strip()

        if current_chunk:
            chunks.append(current_chunk)

        # Filter out chunks that are too short to be useful
        return [c for c in chunks if len(c) >= 100]

    def process(self, raw_text: str, grade: int, subject: str, source_id: str) -> List[Dict]:
        """
        Full processing pipeline: clean → chunk → extract topic per chunk.

        Returns a list of chunk dicts ready to be saved to the DB
        (chunk_id is left as a placeholder; the ingester sets the real ID).
        """
        cleaned = self.clean_text(raw_text)
        chunks = self.chunk_text(cleaned)

        result = []
        for i, chunk_text in enumerate(chunks):
            topic = self.extract_topic(chunk_text)
            result.append({
                "chunk_id": f"{source_id}_CH_{i + 1:02d}",  # ingester may override
                "source_id": source_id,
                "grade": grade,
                "subject": subject,
                "topic": topic,
                "text": chunk_text,
                "chunk_index": i,
            })

        return result
