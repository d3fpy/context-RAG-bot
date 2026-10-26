from . import callbacks, messages  # noqa: F401
from .instance import bot, dp
from .state import load_states


async def main():
    await load_states()
    await dp.start_polling(bot)
