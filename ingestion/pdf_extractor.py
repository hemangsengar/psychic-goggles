"""PDF text extraction using PyMuPDF (fitz)."""

from typing import List, Dict
import fitz  # PyMuPDF


class PDFExtractor:
    """Extracts raw text content from PDF files."""

    def extract_text(self, file_path: str) -> str:
        """Extract all text from a PDF file as a single string."""
        pages = self.extract_pages(file_path)
        return "\n".join(page["text"] for page in pages if page["text"].strip())

    def extract_pages(self, file_path: str) -> List[Dict]:
        """Extract text page by page, returning a list of {page_num, text} dicts."""
        results = []
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                results.append({"page_num": page_num + 1, "text": text})
            doc.close()
        except Exception as e:
            raise RuntimeError(f"Failed to extract text from PDF '{file_path}': {e}") from e
        return results
