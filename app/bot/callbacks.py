import aiohttp
from maxapi.types import CallbackButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from . import backend
from .config import HELP_TEXT, TEACHER_IMG, WELCOME_IMG
from .flows import MATERIALS_LIMIT, ask_backend, show_materials
from .instance import dp
from .keyboards import (
    back_keyboard,
    help_keyboard,
    role_keyboard,
    teacher_keyboard,
)
from .media import edit_with_image, get_media
from .state import save_states, user_states


@dp.message_callback()
async def on_callback(event):
    user_id = event.callback.user.user_id
    payload = event.callback.payload or ""

    if payload == "help":
        await event.message.answer(HELP_TEXT, attachments=[help_keyboard()])

    elif payload == "role_teacher":
        user_states[user_id] = {"role": "teacher", "step": "panel"}
        save_states()
        await edit_with_image(
            event, "Вы учитель. Панель управления:",
            teacher_keyboard(), await get_media(TEACHER_IMG)
        )

    elif payload == "role_student" or payload == "refresh_materials" or payload == "pick_material":
        await show_materials(event, user_id)

    elif payload.startswith("mat_"):
        state = user_states.get(user_id, {})
        options = state.get("options", [])
        try:
            m = options[int(payload[4:])]
        except (ValueError, IndexError):
            await event.message.answer("Список устарел. Напишите /start и выберите роль заново.")
            return
        user_states[user_id] = {
            "role": "student",
            "step": "ready",
            "class_name": m["class_name"],
            "subject": m["subject"],
            "history": [],
        }
        save_states()
        await event.message.edit(
            text=f"Заданные параметры: Класс {m['class_name']}, предмет {m['subject']}.\nЗадайте вопрос.",
            attachments=[back_keyboard()]
        )

    elif payload == "change_role":
        user_states[user_id] = {}
        save_states()
        await edit_with_image(event, "Кто вы?", role_keyboard(),
                              await get_media(WELCOME_IMG))

    elif payload == "upload_book":
        user_states[user_id] = {"role": "teacher", "step": "waiting_file"}
        save_states()
        await event.message.answer("Загрузите файл учебника: (.pdf или .docx)", attachments=[back_keyboard()])

    elif payload == "panel":
        user_states[user_id] = {"role": "teacher", "step": "panel"}
        save_states()
        await edit_with_image(event, "Панель управления:",
                              teacher_keyboard(), await get_media(TEACHER_IMG))

    elif payload == "delete_materials":
        materials = await backend.fetch_materials()
        if not materials:
            await event.message.edit(text="Материалов пока нет.", attachments=[teacher_keyboard()])
            return
        builder = InlineKeyboardBuilder()
        for i, m in enumerate(materials[:MATERIALS_LIMIT]):
            builder.row(CallbackButton(
                text=f"{m['class_name']} · {m['subject']}",
                payload=f"del_{i}"
            ))
        builder.row(CallbackButton(text="Назад", payload="panel"))
        user_states.setdefault(user_id, {})["del_options"] = materials
        save_states()
        text = "Какие материалы удалить?"
        if len(materials) > MATERIALS_LIMIT:
            text += f"\n\nПоказаны первые {MATERIALS_LIMIT} из {len(materials)}."
        await event.message.edit(text=text, attachments=[builder.as_markup()])

    elif payload.startswith("del_"):
        state = user_states.get(user_id, {})
        options = state.get("del_options", [])
        try:
            m = options[int(payload[4:])]
        except (ValueError, IndexError):
            await event.message.answer("Список устарел. Откройте удаление заново.")
            return
        builder = InlineKeyboardBuilder()
        builder.row(CallbackButton(text="Да, удалить", payload=f"delyes_{payload[4:]}"))
        builder.row(CallbackButton(text="Назад", payload="delete_materials"))
        await event.message.edit(
            text=f"Удалить материалы «{m['class_name']} · {m['subject']}» целиком?\n"
                 f"Фрагменты этого учебника тоже будут стёрты.",
            attachments=[builder.as_markup()]
        )

    elif payload.startswith("delyes_"):
        state = user_states.get(user_id, {})
        options = state.get("del_options", [])
        try:
            m = options[int(payload[7:])]
        except (ValueError, IndexError):
            await event.message.answer("Список устарел. Откройте удаление заново.")
            return
        try:
            res = await backend.delete_materials(m["class_name"], m["subject"])
        except aiohttp.ClientError as e:
            print("ошибка удаления", e)
            await event.message.answer(f"Ошибка соединения: {e}")
            return
        state["del_options"] = []
        state.pop("class_name", None)
        state.pop("subject", None)
        save_states()
        await event.message.edit(
            text=f"{res.get('message', 'Готово')}\nПанель управления:",
            attachments=[teacher_keyboard()]
        )

    elif payload == "stats":
        try:
            data = await backend.get_stats()
        except aiohttp.ClientError as e:
            await event.message.answer(f"Ошибка соединения: {e}")
            return
        lines = [
            f"Документов: {data.get('documents', 0)}",
            f"Фрагментов: {data.get('chunks', 0)}",
            "",
        ]
        for m in data.get("materials", []):
            lines.append(
                f"• {m['class_name']} · {m['subject']}: "
                f"{m['documents']} док., {m['chunks']} фрагм."
            )
        await event.message.answer("\n".join(lines), attachments=[teacher_keyboard()])

    elif payload == "more":
        state = user_states.get(user_id, {})
        last = state.get("last_question")
        if not last or state.get("step") != "ready":
            await event.message.answer("Сначала задайте вопрос - потом можно попросить подробнее.")
            return
        await ask_backend(event, user_id, last, detailed=True)

    elif payload == "back":
        state = user_states.get(user_id, {})
        step = state.get("step")

        if step == "waiting_class":
            user_states[user_id] = {
                "role": "teacher",
                "step": "waiting_textbook_name",
                "file_path": state.get("file_path"),
                "filename": state.get("filename"),
            }
            save_states()
            await event.message.edit(
                text="Напишите название учебника (например: Алгебра 7 класс Макарычев).",
                attachments=[back_keyboard()]
            )

        elif state.get("role") == "teacher":
            user_states[user_id] = {"role": "teacher", "step": "panel"}
            save_states()
            await edit_with_image(event, "Панель управления:",
                                  teacher_keyboard(), await get_media(TEACHER_IMG))

        elif state.get("role") == "student":
            if step == "choosing":
                user_states[user_id] = {}
                save_states()
                await edit_with_image(event, "Кто вы?", role_keyboard(),
                                      await get_media(WELCOME_IMG))
            else:
                await show_materials(event, user_id)

        else:
            user_states[user_id] = {}
            save_states()
            await edit_with_image(event, "Кто вы?", role_keyboard(),
                                  await get_media(WELCOME_IMG))
