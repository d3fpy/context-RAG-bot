import asyncio
import json

import aiohttp

from . import backend
from .config import STATE_FILE

user_states: dict = {}


def save_states():
    try:
        STATE_FILE.write_text(json.dumps(user_states, ensure_ascii=False), encoding="utf-8")
    except OSError as e:
        print("не сохранили состояние", e)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_push_states())
    except RuntimeError:
        pass


async def _push_states():
    try:
        await backend.push_states(user_states)
    except aiohttp.ClientError as e:
        print("состояние не ушло на сервер", e)


async def load_states():
    user_states.clear()
    try:
        user_states.update(await backend.fetch_states())
        return
    except aiohttp.ClientError as e:
        print("не удалось забрать состояние с сервера", e)
    try:
        user_states.update(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
