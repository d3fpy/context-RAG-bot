import json
import traceback

from maxapi import ErrorEvent
from maxapi.exceptions import MaxError
from maxapi.types.updates import UpdateUnionAdapter

from . import callbacks, messages  # noqa: F401
from .instance import bot, dp
from .state import load_states


@dp.error()
async def on_error(event: ErrorEvent):
    print("ошибка в обработчике:", type(event.exception).__name__, event.exception)
    traceback.print_exception(event.exception)

    message = getattr(event.update, "message", None)
    if message is None:
        return
    try:
        await message.answer("Не получилось обработать сообщение. Попробуйте ещё раз.")
    except MaxError as e:
        print("не отправилось сообщение об ошибке", e)


def log_attachment_updates():
    original = bot.get_updates

    async def wrapper(*args, **kwargs):
        data = await original(*args, **kwargs)
        for update in (data or {}).get("updates") or []:
            body = (update.get("message") or {}).get("body") or {}
            if not body.get("attachments"):
                continue

            parts = []
            for item in body["attachments"]:
                payload = item.get("payload") or {}
                parts.append(
                    f"{item.get('type')} url={'да' if payload.get('url') else 'нет'} "
                    f"token={'да' if payload.get('token') else 'нет'} "
                    f"имя={item.get('filename')} размер={item.get('size')}"
                )

            try:
                UpdateUnionAdapter.validate_python(update)
                parsed = "ok"
            except Exception as e:
                parsed = f"{type(e).__name__}: {str(e).splitlines()[1] if len(str(e).splitlines()) > 1 else e}"

            print(f"[updates] {update.get('update_type')} | {'; '.join(parts)} | разбор={parsed}")
            print("[updates raw]", json.dumps(update, ensure_ascii=False)[:1500])
        return data

    bot.get_updates = wrapper


async def main():
    log_attachment_updates()
    await load_states()
    await dp.start_polling(bot)
