import google.generativeai as genai
from fastapi import HTTPException
import json
from app.core.config import GOOGLE_API_KEY, GEMINI_MODEL_NAME

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    print("AI Service: Google API Key not configured.")


async def analyze_text_with_gemini(text_to_analyze: str, original_page_number: int = -1) -> list:
    """Sends text to Gemini API for error analysis."""
    if not GOOGLE_API_KEY:
        raise HTTPException(status_code=503, detail="AI Service is not configured (API Key missing).")

    model = genai.GenerativeModel(GEMINI_MODEL_NAME)

    prompt = f"""
        Analyze the following text for grammatical, spelling, punctuation, and stylistic errors.
        The text to analyze (this is text from page {original_page_number if original_page_number != -1 else "unknown"}):
        ---
        {text_to_analyze}
        ---
        For each error found, provide the following information in a JSON array of objects. Each object must contain the following keys:
        - "page_number": {original_page_number if original_page_number != -1 else "unknown"},
        - "original_snippet": The exact short text fragment with the error (up to 15 words).
        - "corrected_snippet": The corrected version of the fragment.
        - "error_type": The type of error (e.g., "spelling", "grammar", "style", "punctuation").
        - "explanation": A brief explanation of the error.

        Example of one object in the JSON array:
        {{
        "page_number": {original_page_number if original_page_number != -1 else 1},
        "original_snippet": "He go to the store.",
        "corrected_snippet": "He goes to the store.",
        "error_type": "grammar",
        "explanation": "Incorrect verb tense. 'Go' should be 'goes' for third-person singular present."
        }}

        If no errors are found, return an empty JSON array [].
        Please return ONLY the JSON array. Do not add any other text, comments, or explanations outside the JSON structure.
        """
    
    response_obj = None # Инициализируем переменную response_obj (чтобы не конфликтовать с именем функции response)
    cleaned_response_text = "" # Инициализируем на случай ошибки до ее определения

    try:
        response_obj = await model.generate_content_async(prompt) # Используем response_obj
        
        # Проверяем, есть ли вообще текст в ответе, прежде чем пытаться его обработать
        if not hasattr(response_obj, 'text') or not response_obj.text:
            # Проверяем prompt_feedback на случай, если запрос был заблокирован
            if hasattr(response_obj, 'prompt_feedback') and response_obj.prompt_feedback:
                 block_reason = str(response_obj.prompt_feedback)
                 print(f"Gemini API request blocked (Page {original_page_number}). Feedback: {block_reason}")
                 return [{"error_type": "AI_Blocked_Request", "explanation": f"Gemini API request blocked: {block_reason}", "page_number": original_page_number, "original_snippet": "N/A", "corrected_snippet": "N/A"}]
            # Если нет текста и нет информации о блокировке, это странная ситуация
            print(f"AI returned no text and no prompt feedback (Page {original_page_number}).")
            return [{"error_type": "AI_Empty_Response", "explanation": "AI returned an empty response without error details.", "page_number": original_page_number, "original_snippet": "N/A", "corrected_snippet": "N/A"}]

        raw_response_text = response_obj.text # Теперь используем response_obj.text
        cleaned_response_text = raw_response_text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
        if cleaned_response_text.endswith("```"):
            cleaned_response_text = cleaned_response_text[:-3]
        cleaned_response_text = cleaned_response_text.strip()
        
        errors = json.loads(cleaned_response_text)
        if not isinstance(errors, list):
             if isinstance(errors, dict) and "original_snippet" in errors:
                 return [errors]
             return []
        return errors
        
    except json.JSONDecodeError as e:
        print(f"AI JSON Decode Error (Page {original_page_number}): {e}. Response: {cleaned_response_text}")
        # В cleaned_response_text может быть полезная информация от AI, почему он не вернул JSON
        return [{"error_type": "AI_Parse_Error", "explanation": f"Could not parse AI response: {e}. Raw AI output: '{cleaned_response_text[:200]}...' (truncated)", "page_number": original_page_number, "original_snippet": "N/A", "corrected_snippet": "N/A"}]
    
    except Exception as e: # Общий обработчик исключений
        error_message = f"Error calling Gemini API (Page {original_page_number}): {str(e)}"
        print(error_message)
        
        # Теперь безопасно проверяем response_obj, так как он был инициализирован
        if response_obj and hasattr(response_obj, 'prompt_feedback') and response_obj.prompt_feedback:
            block_reason = str(response_obj.prompt_feedback)
            print(f"Prompt Feedback: {block_reason}")
            # Возвращаем информацию о блокировке, если она есть
            return [{"error_type": "AI_API_Error_With_Feedback", "explanation": f"Gemini API error: {block_reason}. Original error: {str(e)}", "page_number": original_page_number, "original_snippet": "N/A", "corrected_snippet": "N/A"}]
        
        # Если нет specific feedback, или response_obj не был присвоен (например, ошибка сети ДО вызова API)
        # Поднимаем HTTPException, чтобы FastAPI вернул 500 с деталями
        # Можно также вернуть кастомный JSON с ошибкой, как выше, если не хотим 500
        # Например:
        # return [{"error_type": "AI_Generic_Error", "explanation": error_message, "page_number": original_page_number, "original_snippet": "N/A", "corrected_snippet": "N/A"}]
        # Но для неожиданных ошибок сервера 500 - это нормально.
        raise HTTPException(status_code=500, detail=f"Error communicating with AI API (Page {original_page_number}): {str(e)}")