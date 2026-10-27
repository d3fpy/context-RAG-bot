# Контекст
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-FF4A00?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Ollama](https://img.shields.io/badge/Ollama-000000?logo=ollama&logoColor=white)](https://ollama.com/)

Бот в мессенджере [МАКС](https://max.ru/ideya_fiks_40_bot), который отвечает школьникам на вопросы
по их учебникам и всегда указывает источник: учебник, главу, параграф и страницу.
Всё работает локально - данные учеников не покидают школу.

## Возможности

- Загрузка учебников: учитель отправляет PDF или DOCX прямо в чат, бот спрашивает
  название, класс и предмет
- Вопросы: ученик выбирает класс и предмет кнопками и спрашивает - поиск идёт
  только по его материалам
- Кнопка «Подробнее»: развёрнутый ответ на последний вопрос
- Конспект страницы: достаточно написать `стр 67`
- Панель управления учителя: загрузка, удаление материалов, статистика
- Состояние пользователей хранится в PostgreSQL и переживает перезапуски
- Формулы из ответов переводятся в читаемый вид: `x₁,₂ = (-b ± √(D))/(2a)`

## Архитектура

```
МАКС-бот ──► FastAPI (RAG) ──► PostgreSQL   каталог документов, состояния
                    │           Qdrant      векторный поиск по страницам
                    │           Ollama      локальная LLM :qwen2.5:3b
```

Как устроен поиск: вопрос превращается в вектор (fastembed,
`paraphrase-multilingual-MiniLM-L12-v2`, 384 измерения) и ищется в Qdrant
с фильтром по классу и предмету. Параллельно работает точный поиск по ключевым
словам вопроса. Лучшие фрагменты страниц передаются локальной модели qwen2.5:3b
как контекст с инструкцией отвечать только по тексту учебника. Страницу, где
находится ответ, называет сама модель, а бот сверяет её с найденными фрагментами.

## Запуск

Нужен только Docker:

```bash
docker compose up --build
```

Первичная сборка долгая: скачивается модель эмбеддингов (запекается в образ)
и модель qwen2.5:3b (~2 ГБ, попадает в volume ollama_data). Дальше всё поднимается
автоматически.

Затем в корне проекта создайте файл .env (скопируйте .env.example и вставьте свой токен):

```
MAX_BOT_TOKEN=ваш_токен_из_кабинета_MAX
```

Установите зависимости для бота и запустите его (бот работает локально, обращаясь к API внутри Docker):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run_bot.py
```

Swagger-документация API: http://localhost:8000/docs

Если у вас нет токена бота, API можно проверить через Swagger без запуска бота.

## Структура проекта

```
app/
  main.py             сборка FastAPI: таблицы, роутеры
  config.py           настройки из переменных окружения
  database.py         движок SQLAlchemy (pool_pre_ping)
  models.py           таблицы: documents, chunks, user_states
  schemas.py          pydantic-модели запросов и ответов
  routers/
    upload.py         материалы: загрузка, список, удаление, статистика
    chat.py           вопросы: гибридный поиск + генерация, конспект страницы
    state.py          состояния пользователей бота
  services/
    parser.py         PDF/DOCX → фрагменты, страницы, главы и параграфы
    embedder.py       текст → вектор (fastembed/ONNX)
    qdrant_client.py  поиск, вставка, удаление в Qdrant
    llm.py            промпт и обращение к Ollama
  bot/                бот для МАКС (пакет)
    config.py         токен, пути, тексты
    instance.py       Bot и Dispatcher
    state.py          состояние: сервер + локальный JSON-резерв
    formulas.py       LaTeX → юникод, разбивка длинных сообщений
    keyboards.py      инлайн-клавиатуры
    backend.py        HTTP-запросы к FastAPI
    media.py          картинки-карточки, фидбек «Ищу по вашему вопросу...»
    flows.py          сценарии: выбор материала, вопрос, конспект
    messages.py       обработчики событий чата
    callbacks.py      обработчик кнопок
    main.py           точка входа
run_bot.py            удобный запуск бота
```

## API

Загрузка учебника:

```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@учебник.pdf" \
  -F "class_name=7А" \
  -F "subject=Алгебра" \
  -F "textbook_name=Алгебра 7 класс, Мерзляк"
```

```json
{"ok": true, "document_id": 1, "chunks": 214, "message": "Загружено 214 фрагментов"}
```

Вопрос:

```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Что такое линейное уравнение?", "class_name": "7А", "subject": "Алгебра"}'
```

```json
{
  "answer": "Линейное уравнение - уравнение вида ax + b = 0...",
  "page": 12,
  "textbook": "Алгебра 7 класс, Мерзляк",
  "chapter": "Глава 1",
  "paragraph": "§ 3"
}
```

Остальные эндпоинты: `GET /api/materials`, `DELETE /api/materials`, `GET /api/stats`,
`POST /api/page` (конспект страницы), `GET/PUT/POST/DELETE /api/state`.

## Сервисы и порты

| Сервис | Порт |
|---|---|
| app (FastAPI) | 8000, только localhost |
| postgres | 5432 |
| qdrant | 6333 |
| ollama | 11434 |

## Переменные окружения

Задаются в `docker-compose.yml`, для бота - в `.env`:

| Переменная | По умолчанию |
|---|---|
| DB_URL | postgresql://postgres:postgres@localhost:5432/context |
| QDRANT_HOST | localhost |
| QDRANT_PORT | 6333 |
| COLLECTION_NAME | materials |
| OLLAMA_BASE_URL | http://localhost:11434 |
| API_BASE | http://localhost:8000 |
| MAX_BOT_TOKEN | (токен бота в МАКС) |

## Локальный запуск без Docker

Поднять postgres, qdrant и ollama (`ollama pull qwen2.5:3b`), заполнить `.env`, затем:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
python run_bot.py
```

## Ограничения

- Скан-копии PDF (страницы-картинки) не индексируются - нужен текстовый PDF
- Генерация ответа на CPU занимает 25-40 секунд; на GPU заметно быстрее
- DOCX не имеет страниц - источником всегда будет страница 1
- Номера страниц берутся из самого PDF; если номер не напечатан или напечатан нестандартно,
  страницы считаются от начала файла и могут не совпадать с бумажными
- Точность поиска: гибридный поиск (векторный + по ключевым словам) иногда находит фрагменты с упоминанием термина, но без его определения. Модель в этом случае честно сообщает, что ответа в найденном тексте нет.
