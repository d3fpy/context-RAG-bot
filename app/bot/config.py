import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=ROOT_DIR / ".env")

BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "")
API_BASE = os.getenv("API_BASE", "http://localhost:8000")

STATE_FILE = ROOT_DIR / "bot_state.json"
UPLOAD_DIR = ROOT_DIR / "bot_uploads"
IMG_DIR = Path(__file__).resolve().parents[1] / "assets"
WELCOME_IMG = IMG_DIR / "welcome.jpg"
TEACHER_IMG = IMG_DIR / "teacher.jpg"
STUDENT_IMG = IMG_DIR / "student.jpg"

MAX_LEN = 3500

WELCOME_TEXT = "Привет! Я Контекст — помощник по учебным материалам.\nВыберите роль"

HELP_TEXT = (
    "Что я умею:\n"
    "\n"
    "Ответить на вопрос по учебнику - просто напишите его\n"
    "«Подробнее» - развёрнутый ответ на последний вопрос\n"
    "Конспект страницы - напишите: стр 67\n"
    "Учитель: загрузка и удаление учебников, статистика\n"
    "\n"
    "/start - запуск бота"
)
