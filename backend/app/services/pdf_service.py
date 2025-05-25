import fitz  # PyMuPDF
from fastapi import HTTPException

def extract_text_and_pages_from_pdf(file_content: bytes) -> list:
    """Extracts text page by page from a PDF."""
    pages_content = []
    try:
        doc = fitz.open(stream=file_content, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            pages_content.append({"page_number": page_num + 1, "text": text})
        return pages_content
    except Exception as e:
        # Consider more specific logging/error handling
        raise HTTPException(status_code=500, detail=f"Error extracting text from PDF: {str(e)}")