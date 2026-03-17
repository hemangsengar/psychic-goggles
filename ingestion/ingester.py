"""Main ingestion orchestrator: PDF → chunks → database."""

import os
from uuid import uuid4
from typing import Dict

from models.db_models import SourceDocument, ContentChunk
from ingestion.pdf_extractor import PDFExtractor
from processing.text_processor import TextProcessor


class PDFIngester:
    """Orchestrates the full PDF ingestion pipeline."""

    def __init__(self, db_session):
        self.db = db_session
        self.extractor = PDFExtractor()
        self.processor = TextProcessor()

    def ingest(self, file_path: str, grade: int, subject: str, original_filename: str | None = None) -> Dict:
        """
        Ingest a PDF file end-to-end:
        1. Generate a unique source_id
        2. Save a SourceDocument record (status=processing)
        3. Extract raw text from the PDF
        4. Clean and chunk the text
        5. Save ContentChunk records
        6. Update SourceDocument status to 'processed'

        Returns a summary dict with source_id, filename, and chunks_created.
        Raises on failure after setting status to 'failed'.
        """
        filename = original_filename or os.path.basename(file_path)
        source_id = f"SRC_{uuid4().hex[:6].upper()}"

        # 1. Persist the source document record early so we can track status
        source_doc = SourceDocument(
            source_id=source_id,
            filename=filename,
            grade=grade,
            subject=subject,
            file_path=file_path,
            status="processing",
        )
        self.db.add(source_doc)
        self.db.commit()

        try:
            # 2. Extract text
            raw_text = self.extractor.extract_text(file_path)
            if not raw_text.strip():
                raise ValueError(f"No text could be extracted from '{filename}'.")

            # 3. Process into chunks
            chunk_dicts = self.processor.process(raw_text, grade, subject, source_id)
            if not chunk_dicts:
                raise ValueError(f"Text extracted but no usable chunks produced from '{filename}'.")

            # 4. Persist chunks
            for chunk_data in chunk_dicts:
                chunk = ContentChunk(
                    chunk_id=chunk_data["chunk_id"],
                    source_id=source_id,
                    grade=chunk_data["grade"],
                    subject=chunk_data["subject"],
                    topic=chunk_data["topic"],
                    text=chunk_data["text"],
                    chunk_index=chunk_data["chunk_index"],
                )
                self.db.add(chunk)

            # 5. Mark source as processed
            source_doc.status = "processed"
            self.db.commit()

            return {
                "source_id": source_id,
                "filename": filename,
                "chunks_created": len(chunk_dicts),
                "status": "processed",
            }

        except Exception:
            source_doc.status = "failed"
            self.db.commit()
            raise
