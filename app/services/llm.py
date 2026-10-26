import os
import re

import requests

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

def generate_answer(context: str, question: str, page: int, history: list[str] | None = None,
                    detailed: bool = False) -> str:
    try:
        return _call_ollama(context, question, page, history, detailed)
    except (requests.exceptions.RequestException, KeyError, ValueError) as e:
        print(f"[ollama error] {e}")
        return _stub_answer(context, page)

def _build_prompt(context: str, question: str, page: int, history: list[str] | None = None,
                  detailed: bool = False) -> str:
    prev = ""
    if history:
        prev = (
            "Предыдущий диалог (для контекста, не копируй его в ответ):\n"
            + "\n\n".join(history[-4:]) + "\n\n"
        )

    if detailed:
        length = "Дай развёрнутый ответ: до 6-8 предложений, с примерами и формулами из текста.\n"
    else:
        length = "Отвечай кратко и по существу, максимум 3-4 предложения. Не пересказывай весь текст, а выдели главное.\n"

    return (
        "Ты - школьный ИИ-помощник. Ответь на вопрос ученика, опираясь ТОЛЬКО на текст ниже.\n"
        "Текст разбит на фрагменты, в начале каждого в квадратных скобках указана страница.\n"
        "ВАЖНО: все математические формулы оформляй в формате LaTeX, используя $...$ для строчных формул.\n"
        "Пример: $f(x) = ax + b$, $a^2 + b^2 = c^2$, $(a+b)^2 = a^2 + 2ab + b^2$.\n\n"
        + length +
        "Нужный ответ может быть в любом фрагменте. Сверяй ключевые слова вопроса со словами текста и отвечай по фрагменту, где они есть.\n"
        "Не упоминай в ответе номера фрагментов, квадратные скобки и служебные пометки.\n"
        "Отвечай грамотным литературным русским языком, внимательно согласовывай слова и падежи.\n"
        "Отвечай ТОЛЬКО на русском языке. Не используй слова на других языках (китайском, английском и т.д.)\n\n"
        "Указывай первую страницу, где начинается определение\n"
        "Если точного ответа или определения в тексте нет - честно скажи, что в учебнике этого нет. Не придумывай определения от себя.\n"
        "Если в тексте есть ссылки на другие страницы (например, 'на странице 5 представлено...'), не используй их как источник. Указывай только ту страницу, где находится сам ответ.\n"
        "Если в тексте есть странные или непонятные метафоры (например, «ярлык, повешенный на ящик»), не используй их как определение. Ищи более формальное и понятное объяснение."
        "Если в тексте несколько фрагментов с разных страниц, выбери тот, где ответ наиболее полный. Если определение начинается на одной странице и продолжается на другой, укажи первую страницу (где начинается определение).\n\n"
        + prev +
        f"Текст (стр. {page}):\n{context}\n\n"
        f"Вопрос ученика: {question}\n\n"
    )

def _call_ollama(context: str, question: str, page: int, history: list[str] | None = None,
                 detailed: bool = False) -> str:
    prompt = _build_prompt(context, question, page, history, detailed)
    
    resp = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": "qwen2.5:3b",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": 800  if detailed else 200
            }
        },
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json()["response"]

def _stub_answer(context: str, page: int) -> str:
    return (
        f"[Тестовый режим - Ollama недоступна]\n\n"
        f"Нашёл в материалах (стр. {page}):\n\n"
        f"{context[:400]}...\n\n"
        f"Источник: страница {page}"
    )
def remove_chinese(text: str) -> str:
    return re.sub(r'[\u4e00-\u9fff]+', '', text)