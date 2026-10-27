import asyncio
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
from .media import edit_status, get_media, send_status
from .state import save_states, user_states


async def _send_welcome(event, user_id: int):
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


@dp.bot_started()
async def on_start(event: BotStarted):
    user_states.setdefault(event.user.user_id, {})
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
    user_states[user_id] = {}
    save_states()
    await _send_welcome(event, user_id)


@dp.message_created(F.message.body.attachments)
async def on_file(event: MessageCreated):
    user_id = event.message.sender.user_id
    attachments = event.message.body.attachments or []
    print("[on_file] вложения:", [a.type for a in attachments])

    attachment = next((a for a in attachments if a.type == "file"), None)
    if attachment is None:
        await event.message.answer(
            "Похоже, это не файл. Загрузите учебник документом в формате PDF или DOCX, а не картинкой.",
        )
        return

    file_name = Path(attachment.filename or "book.pdf").name
    if not file_name.lower().endswith((".pdf", ".docx")):
        await event.message.answer("Принимаются только файлы PDF и DOCX.", attachments=[teacher_keyboard()])
        return

    file_url = getattr(attachment.payload, "url", None)
    if not file_url:
        await event.message.answer(
            "MAX не прислал ссылку на файл, скачать его не получилось. Пришлите файл ещё раз.",
            attachments=[teacher_keyboard()],
        )
        return

    status_id = await send_status(event, "Скачиваю файл, подождите немного...")
    print("[on_file] качаю:", file_name)
    shown = -1
    progress_lock = asyncio.Lock()

    async def progress(percent: int) -> None:
        nonlocal shown
        step = percent // 20 * 20
        async with progress_lock:
            if status_id is None or step <= shown:
                return
            shown = step
        await edit_status(status_id, f"Скачиваю файл... {percent}%")

    file_data = await _download(file_url, progress)
    if file_data is None:
        await _reply(event, status_id, "Не получилось скачать файл из чата. Пришлите его ещё раз.", teacher_keyboard())
        return
    print("[on_file] скачано, байт:", len(file_data))

    if not _looks_like_book(file_data):
        await _reply(event, status_id, "Файл не похож на PDF или DOCX. Проверьте формат и пришлите его снова.", teacher_keyboard())
        return

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / f"{user_id}_{file_name}"
    try:
        file_path.write_bytes(file_data)
    except OSError as e:
        print("не сохранили файл", e)
        await _reply(event, status_id, "Не получилось сохранить файл. Попробуйте ещё раз.", teacher_keyboard())
        return

    user_states[user_id] = {
        "role": "teacher",
        "step": "waiting_textbook_name",
        "file_path": str(file_path),
        "filename": file_name,
    }
    save_states()
    await _reply(
        event,
        status_id,
        "Файл получен. Напишите название материала (например: Алгебра 7 класс Макарычев).",
    )


async def _reply(event, status_id, text, kb=None) -> None:
    if await edit_status(status_id, text, kb):
        return
    await event.message.answer(text, attachments=[kb] if kb else None)


CHUNK_BYTES = 1024 * 1024
DOWNLOAD_STREAMS = 8


async def _download(url: str, on_progress=None) -> bytes | None:
    timeout = aiohttp.ClientTimeout(total=900)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            total = await _file_size(session, url)
            if not total:
                return await _download_single(session, url, on_progress)

            bounds = [
                (start, min(start + CHUNK_BYTES, total) - 1)
                for start in range(0, total, CHUNK_BYTES)
            ]
            parts = [b""] * len(bounds)
            loaded = 0
            counter = asyncio.Lock()
            semaphore = asyncio.Semaphore(DOWNLOAD_STREAMS)

            async def fetch(index: int, start: int, end: int) -> None:
                nonlocal loaded
                async with semaphore:
                    headers = {"Range": f"bytes={start}-{end}"}
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 206:
                            raise RuntimeError(f"код {resp.status}")
                        parts[index] = await resp.read()

                async with counter:
                    loaded += len(parts[index])
                    percent = min(100, loaded * 100 // total)
                if on_progress is not None:
                    await on_progress(percent)

            await asyncio.gather(*(fetch(i, s, e) for i, (s, e) in enumerate(bounds)))
            return b"".join(parts)
    except (TimeoutError, aiohttp.ClientError, RuntimeError) as e:
        print("файл не скачался", e)
        return None


async def _file_size(session, url: str) -> int | None:
    async with session.get(url, headers={"Range": "bytes=0-0"}) as resp:
        if resp.status == 206:
            total = resp.headers.get("Content-Range", "").rpartition("/")[2]
            return int(total) if total.isdigit() else None
        if resp.status == 200 and resp.content_length:
            return resp.content_length
    return None


async def _download_single(session, url: str, on_progress=None) -> bytes | None:
    async with session.get(url) as resp:
        if resp.status != 200:
            print("файл не скачался, код:", resp.status)
            return None

        total = resp.content_length or 0
        chunks = []
        loaded = 0
        async for chunk in resp.content.iter_chunked(256 * 1024):
            chunks.append(chunk)
            loaded += len(chunk)
            if on_progress is not None and total:
                await on_progress(min(100, loaded * 100 // total))
        return b"".join(chunks)


def _looks_like_book(data: bytes) -> bool:
    return data.startswith(b"%PDF") or data.startswith(b"PK")


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
        await _send_welcome(event, user_id)
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

        message_id = await send_status(event, "Обрабатываю данные...")
        try:
            status, res = await backend.upload_material(
                file_data,
                state.get("filename", "book.pdf"),
                class_name,
                subject,
                state.get("textbook_name", "Учебник"),
            )
            if status == 200 and res.get("ok"):
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
                await edit_status(
                    message_id,
                    f"Учебник загружен. Фрагментов: {res.get('chunks', 0)}.",
                    enter_another_keyboard(),
                )
            else:
                await edit_status(
                    message_id,
                    res.get("message") or "Ошибка при загрузке учебника. Попробуйте позже.",
                    teacher_keyboard(),
                )
        except aiohttp.ClientError as e:
            print("ошибка соединения", e)
            await edit_status(message_id, f"Ошибка соединения: {e}", teacher_keyboard())
        return

    if step == "ready":
        page_match = PAGE_RE.match(text)
        if page_match:
            await page_backend(event, user_id, int(page_match.group(1)))
            return

        await ask_backend(event, user_id, text)
        return

    if role == "student" and step == "choosing":
        await event.message.answer("Сначала выберите класс и предмет кнопками выше.", attachments=[change_role_keyboard()])
        return

    await event.message.answer(
        "Не понял. Напишите /start, чтобы выбрать роль.",
        attachments=[role_keyboard()],
    )
