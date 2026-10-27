from pathlib import Path

from maxapi.exceptions import MaxError
from maxapi.types import InputMedia

from .formulas import split_message
from .instance import bot

media_cache = {}

STATUS_TEXT = "Ищу по вашему вопросу..."


async def get_media(path: Path):
    key = str(path)
    if key in media_cache:
        return media_cache[key]

    if not path.exists():
        return None

    try:
        media_cache[key] = await bot.upload_media(InputMedia(str(path), "image"))
    except MaxError as e:
        print("не загрузилась картинка", path.name, e)
        return None
    return media_cache[key]


async def edit_with_image(event, text, keyboard, image):
    if image is not None:
        try:
            await event.message.edit(text=text, attachments=[image, keyboard])
            return
        except MaxError as e:
            print("не получилось отредактировать с картинкой", e)
    await event.message.edit(text=text, attachments=[keyboard])


async def send_status(event, text: str = STATUS_TEXT):
    try:
        sent = await event.message.answer(text)
    except MaxError as e:
        print("не отправился статус", e)
        return None

    if sent is None or sent.message is None:
        return None
    return sent.message.body.mid


async def edit_status(message_id, text, kb=None):
    if message_id is None:
        return False
    try:
        await bot.edit_message(
            message_id=message_id,
            text=text,
            attachments=[kb] if kb else None,
        )
        return True
    except (MaxError, ValueError) as e:
        print("не получилось отредактировать сообщение", e)
        return False


async def answer_with_feedback(event, text: str, kb=None, message_id=None):
    parts = split_message(text)

    if not await edit_status(message_id, parts[0]):
        await event.message.answer(parts[0])

    for part in parts[1:]:
        await event.message.answer(part)

    if kb:
        await event.message.answer("Выберите действие:", attachments=[kb])
