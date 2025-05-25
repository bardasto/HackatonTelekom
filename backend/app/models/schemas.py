from pydantic import BaseModel
from typing import List, Union

class ErrorDetail(BaseModel):
    page_number: Union[int, str] # Can be int or "unknown"
    original_snippet: str
    corrected_snippet: str
    error_type: str
    explanation: str

class AnalysisResponse(BaseModel):
    filename: str
    errors: List[ErrorDetail]
    total_pages: int