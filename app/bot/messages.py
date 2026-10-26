from pathlib import Path

import aiohttp
from maxapi import F
from maxapi.exceptions import MaxError
from maxapi.types import BotStarted, Command, MessageCreated

from . import backend
from .config import UPLOAD_DIR, WELCOME_IMG, WELCOME_TEXT
from .flows import PAGE_RE, ask_backend, page_backend
from .instance import bot, dp
from .keyboards import (
    back_keyboard,
    change_role_keyboard,
    enter_another_keyboard,
    role_keyboard,
    teacher_keyboard,
)
from .media import get_media
from .state import save_states, user_states


@dp.bot_started()
async def on_start(event: BotStarted):
    user_id = event.user.user_id
    user_states.setdefault(user_id, {})
    save_states()
    img = await get_media(WELCOME_IMG)
    if img is not None:
        try:
            await bot.send_message(
                chat_id=event.chat_id,
                text=WELCOME_TEXT,
                attachments=[img, role_keyboard()]
            )
            return
        except MaxError as e:
            print("не отправилось с картинкой", e)
    await bot.send_message(
        chat_id=event.chat_id,
        text=WELCOME_TEXT,
        attachments=[role_keyboard()]
    )


@dp.message_created(Command("start"))
async def on_start_command(event: MessageCreated):
    user_id = event.message.sender.user_id
    print("[debug] /start получен от", event.message.sender.user_id)
    user_states.setdefault(user_id, {})
    save_states()
    img = await get_media(WELCOME_IMG)
    if img is not None:
        try:
            await event.message.answer(WELCOME_TEXT, attachments=[img, role_keyboard()])
            return
        except MaxError as e:
            print("не отправилось с картинкой", e)
    await event.message.answer(WELCOME_TEXT, attachments=[role_keyboard()])


@dp.message_created(F.message.body.attachments)
async def on_file(event: MessageCreated):
    user_id = event.message.sender.user_id
    attachment = event.message.body.attachments[0]

    if attachment.type != "file":
        await event.message.answer(
            "Похоже, это не файл. Загрузите учебник документом в формате PDF или DOCX, а не картинкой.",
        )
        return

    file_name = (attachment.filename or "").lower()
    if not file_name.endswith((".pdf", ".docx")):
        await event.message.answer("Принимаются только файлы PDF и DOCX.", attachments=[teacher_keyboard()])
        return

    file_url = attachment.payload.url

    try:
        async with aiohttp.ClientSession() as session, session.get(file_url) as resp:
            file_data = await resp.read()
    except aiohttp.ClientError as e:
        await event.message.answer(f"Ошибка при скачивании файла: {e}", attachments=[teacher_keyboard()])
        return

    UPLOAD_DIR.mkdir(exist_ok=True)
    file_path = UPLOAD_DIR / f"{user_id}_{attachment.filename}"
    try:
        file_path.write_bytes(file_data)
    except OSError as e:
        print("не сохранили файл", e)
        await event.message.answer("Не получилось сохранить файл. Попробуйте ещё раз.", attachments=[teacher_keyboard()])
        return

    user_states[user_id] = {
        "role": "teacher",
        "step": "waiting_textbook_name",
        "file_path": str(file_path),
        "filename": attachment.filename,
    }
    save_states()
    await event.message.answer(
        "Файл получен. Напишите название материала (например: Алгебра 7 класс Макарычев).",
    )


@dp.message_created(F.message.body.text)
async def on_text(event: MessageCreated):
    user_id = event.message.sender.user_id
    state = user_states.get(user_id, {})
    text = event.message.body.text

    if text.startswith("/"):
        return

    step = state.get("step")
    role = state.get("role")

    if not role:
        img = await get_media(WELCOME_IMG)
        if img is not None:
            try:
                await event.message.answer(WELCOME_TEXT, attachments=[img, role_keyboard()])
                return
            except MaxError as e:
                print("не отправилось с картинкой", e)
        await event.message.answer(WELCOME_TEXT, attachments=[role_keyboard()])
        return

    if role == "teacher" and step == "panel":
        await event.message.answer("Выберите действие кнопками на панели.", attachments=[teacher_keyboard()])
        return

    if role == "teacher" and step == "waiting_file":
        await event.message.answer("Загрузите файл учебника (PDF или DOCX) или нажмите «Назад».", attachments=[back_keyboard()])
        return

    if role == "teacher" and step == "waiting_textbook_name":
        textbook_name = text.strip()
        if not textbook_name:
            await event.message.answer("Название не может быть пустым. Напишите название учебника.", attachments=[teacher_keyboard()])
            return
        user_states[user_id] = {
            "role": "teacher",
            "step": "waiting_class",
            "file_path": state.get("file_path"),
            "filename": state.get("filename"),
            "textbook_name": textbook_name,
        }
        save_states()
        await event.message.answer(
            "Теперь напишите класс и предмет через запятую.\n"
            "Пример: 7А, Алгебра",
        )
        return

    if role == "teacher" and step == "waiting_class":
        parts = [p.strip() for p in text.split(",")]
        if len(parts) < 2:
            await event.message.answer(
                "Укажите класс и предмет через запятую.\n"
                "Пример: 7А, Алгебра",
            )
            return

        class_name, subject = parts[0], parts[1]

        file_path = Path(state.get("file_path", ""))
        if not file_path.exists():
            user_states[user_id] = {"role": "teacher", "step": "waiting_file"}
            save_states()
            await event.message.answer("Файл потерялся. Загрузите учебник заново.", attachments=[teacher_keyboard()])
            return
        file_data = file_path.read_bytes()

        status_msg = await event.message.answer("Обрабатываю данные...")
        print("STATUS_MSG:", status_msg)
        try:
            status, res = await backend.upload_material(
                file_data,
                state.get("filename", "book.pdf"),
                class_name,
                subject,
                state.get("textbook_name", "Учебник"),
            )
            if status == 200:
                user_states[user_id] = {
                    "role": "teacher",
                    "step": "ready",
                    "class_name": class_name,
                    "subject": subject,
                    "history": [],
                }
                save_states()
                try:
                    file_path.unlink()
                except OSError:
                    pass
                await bot.edit_message(
                    message_id=status_msg.message.body.mid,
                    text=f"Учебник загружен. Фрагментов: {res.get('chunks', 0)}.",
                    attachments=[enter_another_keyboard()]
                )
            else:
                await bot.edit_message(
                    message_id=status_msg.message.body.mid,
                    text="Ошибка при загрузке учебника. Попробуйте позже.",
                    attachments=[teacher_keyboard()]
                )
        except aiohttp.ClientError as e:
            print("ошибка соединения", e)
            await bot.edit_message(
                message_id=status_msg.message.body.mid,
                text=f"Ошибка соединения: {e}",
                attachments=[teacher_keyboard()]
            )
        return

    if step == "ready":
        page_match = PAGE_RE.match(text)
        print(f"debug: step=ready, text={text}")
        if page_match:
            await page_backend(event, user_id, int(page_match.group(1)))
            return

        await event.message.answer("Ищу в материалах...")
        await ask_backend(event, user_id, text)
        return

    if role == "student" and step == "choosing":
        await event.message.answer("Сначала выберите класс и предмет кнопками выше.", attachments=[change_role_keyboard()])
        return