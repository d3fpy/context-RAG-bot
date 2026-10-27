import asyncio
import json

import aiohttp

from . import backend
from .config import STATE_FILE

user_states: dict = {}


def _normalize(raw: dict) -> dict:
    result = {}
    for key, value in raw.items():
        try:
            user_id = int(key)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            result[user_id] = value
    return result


def save_states():
    try:
        STATE_FILE.write_text(
            json.dumps({str(k): v for k, v in user_states.items()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except (OSError, TypeError) as e:
        print("не сохранили состояние", e)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_push_states())
    except RuntimeError:
        pass


async def _push_states():
    try:
        await backend.push_states({str(k): v for k, v in user_states.items()})
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        print("состояние не ушло на сервер", e)


async def load_states():
    user_states.clear()
    try:
        user_states.update(_normalize(await backend.fetch_states()))
        return
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        print("не удалось забрать состояние с сервера", e)
    try:
        user_states.update(_normalize(json.loads(STATE_FILE.read_text(encoding="utf-8"))))
    except (OSError, ValueError):
        pass
