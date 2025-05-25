from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Body
from fastapi.responses import StreamingResponse # Для отправки файла клиенту
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any # Для типизации
import io # Для работы с BytesIO как с файлом
import json # Для разбора JSON строки с ошибками
import os 

# Импорты из нашего проекта
from app.services.pdf_service import extract_text_and_pages_from_pdf
from app.services.ai_service import analyze_text_with_gemini
from app.services.corrected_pdf_service import create_pdf_with_corrected_text 
# apply_corrections_to_text используется внутри create_pdf_with_corrected_text, его отдельно не вызываем в main
from app.models.schemas import AnalysisResponse, ErrorDetail # Pydantic модели для валидации и ответа
from app.core.config import GOOGLE_API_KEY # Конфигурация API ключа

# Инициализация FastAPI приложения
app = FastAPI(
    title="AI PDF Proofreader API",
    description="API for analyzing PDF files for errors using AI and downloading corrected versions.",
    version="1.0.0"
)

# Проверка наличия API ключа при старте (для информации в логах)
if not GOOGLE_API_KEY:
    print("WARNING from main.py: GOOGLE_API_KEY is not set. AI functionalities will be impaired or unavailable.")

# Настройка CORS (Cross-Origin Resource Sharing)
# Позволяет фронтенду (работающему на другом порту/домене) обращаться к этому API
origins = [
    "http://localhost",         # Для Docker Compose, если фронтенд будет обращаться к бэкенду по имени сервиса
    "http://localhost:3000",    # Стандартный порт для React dev server
    "http://127.0.0.1:3000",    # Альтернативный localhost
    # Добавьте сюда URL вашего развернутого фронтенда, если он будет
    # "https://your-frontend-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Список разрешенных источников
    allow_credentials=True,      # Разрешить куки и заголовки авторизации
    allow_methods=["*"],         # Разрешить все HTTP методы (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],         # Разрешить все заголовки
)

# Корневой эндпоинт для проверки, что API работает
@app.get("/")
async def read_root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Welcome to AI PDF Proofreader API. Use /docs for API documentation."}

# Эндпоинт для загрузки PDF, анализа и получения списка ошибок
@app.post("/api/v1/analyze-pdf/", response_model=AnalysisResponse)
async def upload_and_analyze_pdf(file: UploadFile = File(..., description="PDF file to be analyzed.")):
    """
    Uploads a PDF file, analyzes its text content page by page using an AI model,
    and returns a list of detected errors along with metadata.
    """
    if not file.content_type == "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF files are allowed.")

    if not GOOGLE_API_KEY:
         raise HTTPException(status_code=503, detail="AI Service is not available due to missing API key configuration on the server.")

    try:
        # Читаем содержимое файла
        contents = await file.read()
        
        # Извлекаем текст постранично
        pages_data = extract_text_and_pages_from_pdf(contents)
        if not pages_data: # Если PDF пустой или текст не извлечен
            raise HTTPException(status_code=422, detail="Could not extract any text from the PDF or the PDF is empty.")

        all_errors_details: list[ErrorDetail] = [] # Список для хранения всех найденных ошибок
        
        # Анализируем текст каждой страницы
        for page_info in pages_data:
            page_text = page_info.get("text", "")
            page_num = page_info.get("page_number", 0) # Нумерация страниц начинается с 1 в pages_data
            
            if page_text.strip(): # Анализируем, только если на странице есть текст
                errors_on_page_raw = await analyze_text_with_gemini(page_text, original_page_number=page_num)
                
                # Преобразуем "сырые" ошибки от AI в нашу Pydantic модель ErrorDetail
                for err_data in errors_on_page_raw:
                    # Убедимся, что page_number корректный
                    current_error_page_num = err_data.get("page_number", page_num)
                    if isinstance(current_error_page_num, str) and current_error_page_num.lower() == "unknown":
                        current_error_page_num = page_num # Если AI не указал, берем номер текущей обрабатываемой страницы

                    processed_error = ErrorDetail(
                        page_number=current_error_page_num,
                        original_snippet=err_data.get("original_snippet", "N/A"),
                        corrected_snippet=err_data.get("corrected_snippet", "N/A"),
                        error_type=err_data.get("error_type", "Unknown"),
                        explanation=err_data.get("explanation", "No explanation provided.")
                    )
                    all_errors_details.append(processed_error)
        
        return AnalysisResponse(
            filename=file.filename, 
            errors=all_errors_details, 
            total_pages=len(pages_data)
        )

    except HTTPException as e:
        # Перебрасываем HTTP исключения, чтобы FastAPI их правильно обработал
        raise e
    except Exception as e:
        # Логируем неожиданные ошибки на сервере
        print(f"Unexpected server error during PDF analysis: {e}") # В продакшене лучше использовать полноценное логирование
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred during analysis: {str(e)}")


# Новый эндпоинт для скачивания PDF с примененными исправлениями
@app.post("/api/v1/download-corrected-pdf/")
async def download_corrected_pdf_endpoint(
    file: UploadFile = File(..., description="The original PDF file (re-uploaded)."),
    errors_json_str: str = Form(..., description="A JSON string representing the list of errors found by the AI.")
):
    """
    Accepts the original PDF file (re-uploaded) and a JSON string of errors.
    It then extracts text from the PDF, applies the corrections (based on the provided errors),
    generates a new PDF document with the corrected text, and returns it for download.
    The original PDF formatting (layouts, images, fonts) is NOT preserved; 
    the new PDF contains only the corrected text in a simple layout.
    """
    if not file.content_type == "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid file type for correction. Only PDF is allowed.")

    try:
        # Преобразуем строку JSON с ошибками в Python список словарей
        # Эти ошибки должны быть в формате, совместимом с ожидаемым `create_pdf_with_corrected_text`
        # (т.е., список словарей, каждый из которых имеет ключи 'page_number', 'original_snippet', 'corrected_snippet')
        errors_list_of_dicts: List[Dict[str, Any]] = json.loads(errors_json_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for 'errors_json_str'. Expected a list of error objects.")


    try:
        # Читаем содержимое оригинального PDF файла (который пользователь снова загрузил)
        pdf_contents = await file.read()
        
        # 1. Извлекаем текст из оригинального PDF
        pages_data = extract_text_and_pages_from_pdf(pdf_contents)
        if not pages_data:
            raise HTTPException(status_code=422, detail="Could not extract text from the provided PDF for correction.")

        # 2. Создаем новый PDF файл с примененными исправлениями
        # `errors_list_of_dicts` используется для применения исправлений
        pdf_buffer: io.BytesIO = create_pdf_with_corrected_text(pages_data, errors_list_of_dicts)
        
        # Формируем имя для скачиваемого файла
        base_filename, _ = os.path.splitext(file.filename) if file.filename else ("document", ".pdf")
        corrected_filename = f"corrected_{base_filename}.pdf"
        
        # Отправляем сгенерированный PDF как поток байт
        return StreamingResponse(
            iter([pdf_buffer.getvalue()]), # getvalue() возвращает все байты из буфера
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=\"{corrected_filename}\""} # Кавычки вокруг имени файла важны для имен с пробелами
        )
    except HTTPException as e:
        raise e # Перебрасываем известные HTTP исключения
    except Exception as e:
        # Логируем неожиданные ошибки
        print(f"Error generating corrected PDF: {e}") # В продакшене - полноценное логирование
        raise HTTPException(status_code=500, detail=f"Could not generate corrected PDF: {str(e)}")

# Если этот файл запускается напрямую (например, uvicorn main:app)
# Эта часть не нужна, если используется docker-compose с командой uvicorn.
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)