import aiohttp

from .config import API_BASE


async def fetch_materials() -> list[dict]:
    try:
        async with aiohttp.ClientSession() as session, session.get(f"{API_BASE}/api/materials", timeout=15) as r:
            if r.status == 200:
                return await r.json()
    except aiohttp.ClientError as e:
        print("материалы не пришли", e)
    return []


async def fetch_states() -> dict:
    async with aiohttp.ClientSession() as session, session.get(f"{API_BASE}/api/state", timeout=15) as r:
        return await r.json()


async def push_states(states: dict) -> dict:
    async with aiohttp.ClientSession() as session, session.put(f"{API_BASE}/api/state", json=states, timeout=15) as r:
        if r.status != 200:
            print("состояние не сохранилось:", r.status, await r.text())
            return {}
        return await r.json()


async def ask(payload: dict) -> tuple[int, dict]:
    async with aiohttp.ClientSession() as session, session.post(f"{API_BASE}/api/ask", json=payload, timeout=180) as r:
        return r.status, await r.json()


async def page_summary(body: dict) -> tuple[int, dict]:
    async with aiohttp.ClientSession() as session, session.post(f"{API_BASE}/api/page", json=body, timeout=180) as r:
        return r.status, await r.json()


async def upload_material(file_data: bytes, filename: str, class_name: str,
                          subject: str, textbook_name: str) -> tuple[int, dict]:
    form = aiohttp.FormData()
    form.add_field("file", file_data, filename=filename)
    form.add_field("class_name", class_name)
    form.add_field("subject", subject)
    form.add_field("textbook_name", textbook_name)

    async with aiohttp.ClientSession() as session, session.post(f"{API_BASE}/api/upload", data=form, timeout=300) as r:
        return r.status, await r.json()


async def delete_materials(class_name: str, subject: str) -> dict:
    async with aiohttp.ClientSession() as session, session.delete(
        f"{API_BASE}/api/materials",
        params={"class_name": class_name, "subject": subject},
        timeout=60,
    ) as r:
        return await r.json()


async def get_stats() -> dict:
    async with aiohttp.ClientSession() as session, session.get(f"{API_BASE}/api/stats", timeout=15) as r:
        return await r.json()
