import re

import aiohttp
from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from . import backend
from .config import STUDENT_IMG
from .formulas import clean_formulas
from .keyboards import (
    back_keyboard,
    change_role_keyboard,
    student_after_keyboard,
    teacher_after_keyboard,
)
from .media import answer_with_feedback, edit_with_image, get_media
from .state import save_states, user_states

PAGE_RE = re.compile(r"^\s*(?:стр\.?|страница|конспект)\s*(\d+)\s*$", re.IGNORECASE)


async def show_materials(event, user_id):
    materials = await backend.fetch_materials()
    img = await get_media(STUDENT_IMG)
    if not materials:
        user_states[user_id] = {"role": "student", "step": "choosing"}
        save_states()
        await edit_with_image(
            event,
            "Вы ученик. Материалов пока нет - попросите учителя загрузить материал.",
            back_keyboard(),
            img
        )
        return
    builder = InlineKeyboardBuilder()
    for i, m in enumerate(materials[:12]):
        builder.row(CallbackButton(
            text=f"{m['class_name']} · {m['subject']}",
            payload=f"mat_{i}"
        ))
    builder.row(CallbackButton(text="Обновить список", payload="refresh_materials"))
    builder.row(CallbackButton(text="Сменить роль", payload="change_role"))
    user_states[user_id] = {"role": "student", "step": "choosing", "options": materials}
    save_states()
    await edit_with_image(event, "Выберите класс и предмет:", builder.as_markup(), img)


async def ask_backend(event, user_id, text, detailed=False):
    state = user_states.get(user_id, {})
    class_name = state.get("class_name")
    subject = state.get("subject")

    if not class_name or not subject:
        await event.message.answer("Сначала выберите класс и предмет: /start.", attachments=[change_role_keyboard()])
        return

    history = state.get("history", [])
    payload = {
        "question": text,
        "class_name": class_name,
        "subject": subject,
        "history": history[-4:],
        "detailed": detailed,
    }
    try:
        status, data = await backend.ask(payload)
        if status == 200:
            answer = data.get("answer", "Не удалось получить ответ.")
            page = data.get("page", 0)
            textbook = data.get("textbook", "")

            source = (f"\n\nИсточник: {textbook or 'учебник'}, страница {page}"
                      if page > 0 else "")

            clean = clean_formulas(answer)
            history.append(f"Вопрос: {text}\nОтвет: {clean[:400]}")
            state["history"] = history[-8:]
            state["last_question"] = text
            save_states()

            kb = student_after_keyboard() if state.get("role") == "student" else teacher_after_keyboard()
            prefix = "Подробнее:\n\n" if detailed else ""
            await answer_with_feedback(event, f"{prefix}{clean}{source}", kb=kb)
        else:
            await event.message.answer("Ошибка на стороне сервера. Попробуйте позже.", attachments=[change_role_keyboard()])
    except aiohttp.ClientError as e:
        await event.message.answer(f"Ошибка соединения: {e}", attachments=[change_role_keyboard()])

async def page_backend(event, user_id, page):
    state = user_states.get(user_id, {})
    body = {
        "class_name": state.get("class_name"),
        "subject": state.get("subject"),
        "page": page,
    }
    try:
        status, data = await backend.page_summary(body)
        if status == 200:
            clean = clean_formulas(data.get("answer", ""))
            textbook = data.get("textbook", "")
            chapter = data.get("chapter", "")
            src = f"\n\nИсточник: {textbook or 'учебник'}"
            if chapter:
                src += f", {chapter}"
            src += f", страница {page}"
            await answer_with_feedback(event, f"Конспект страницы {page}:\n\n{clean}{src}")
        else:
            await event.message.answer("Ошибка на стороне сервера. Попробуйте позже.")
    except aiohttp.ClientError as e:
        await event.message.answer(f"Ошибка соединения: {e}")
