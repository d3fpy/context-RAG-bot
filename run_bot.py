import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.bot.config import BOT_TOKEN
from app.bot.main import main


def main_entry():
    if not BOT_TOKEN:
        print("Токен бота не был найден. Впишите его в .env")
        return
    print('Бот запущен!')
    asyncio.run(main())


if __name__ == "__main__":
    main_entry()