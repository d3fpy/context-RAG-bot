from pathlib import Path

from maxapi.exceptions import MaxError
from maxapi.types import InputMedia

from .formulas import split_message
from .instance import bot

media_cache = {}


async def get_media(path: Path):
    key = str(path)
    if key not in media_cache:
        media_cache[key] = None
        if path.exists():
            try:
                media_cache[key] = await bot.upload_media(InputMedia(str(path), "image"))
            except MaxError as e:
                print("не загрузилась картинка", path.name, e)
    return media_cache[key]


async def edit_with_image(event, text, keyboard, image):
    if image is not None:
        try:
            await event.message.edit(text=text, attachments=[image, keyboard])
            return
        except MaxError as e:
            print("не получилось отредактировать с картинкой", e)
    await event.message.edit(text=text, attachments=[keyboard])


async def answer_with_feedback(event, text: str, kb=None):
    parts = split_message(text)
    try:
        sent = await event.message.answer("Ищу по вашему вопросу...")
        await sent.edit(text=parts[0])
        for part in parts[1:]:
            await event.message.answer(part)
        if kb:
            await event.message.answer("Выберите действие:", attachments=[kb])
        return
    except (AttributeError, KeyError) as e:
        print("не получилось отредактировать сообщение", e)
    for i, part in enumerate(parts):
        attach = [kb] if (kb and i == len(parts) - 1) else None
        await event.message.answer(part, attachments=attach)
