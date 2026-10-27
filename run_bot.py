import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.bot.config import BOT_TOKEN


def main_entry():
    if not BOT_TOKEN:
        print("Токен бота не был найден. Впишите MAX_BOT_TOKEN в .env")
        return

    from app.bot.main import main

    print("Бот запущен!")
    asyncio.run(main())


if __name__ == "__main__":
    main_entry()
