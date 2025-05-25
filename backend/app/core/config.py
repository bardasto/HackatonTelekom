import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=dotenv_path)

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
# ИЗМЕНЕНИЕ ЗДЕСЬ: Используем точное имя из списка доступных моделей
GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "models/gemini-1.5-flash-latest")

if not GOOGLE_API_KEY:
    print("CRITICAL: GOOGLE_API_KEY is not set.")