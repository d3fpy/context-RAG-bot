import io
import re
from collections import Counter

import docx
import pypdf


def parse_file(content: bytes, filename: str) -> list[dict]:
    name = filename.lower()

    if name.endswith(".pdf"):
        return _parse_pdf(content)
    if name.endswith(".docx"):
        return _parse_docx(content)

    raise ValueError("Поддерживаются только .pdf и .docx")


def _clean_chapter(raw: str) -> str:
    s = re.sub(r'(?<=[IVXivx])(?=\d)', ' ', raw)
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'[\s.,;:]*\d{1,4}\s*$', '', s)
    if s.lower().rstrip(' .,;:') == 'глава':
        return re.sub(r'\s+', ' ', raw).strip()[:80]
    return s.strip(' .,;:')[:80]


def _printed_number(txt: str) -> int | None:
    for line in txt.splitlines()[:3] + txt.splitlines()[-3:]:
        s = line.strip().strip('–—- ')
        if s.isdigit() and len(s) <= 4:
            return int(s)
    return None


def _page_offset(printed: dict[int, int]) -> int:
    if len(printed) < 5:
        return 0
    diffs = [value - (idx + 1) for idx, value in printed.items()]
    common, count = Counter(diffs).most_common(1)[0]
    return common if count >= len(diffs) * 0.5 else 0


def _parse_pdf(content: bytes) -> list[dict]:
    reader = pypdf.PdfReader(io.BytesIO(content))

    current_chapter = ""
    current_paragraph = ""
    printed: dict[int, int] = {}
    pages: list[tuple[int, str, str, str]] = []

    for i, page in enumerate(reader.pages):
        txt = page.extract_text()
        if not txt or not txt.strip():
            continue

        number = _printed_number(txt)
        if number is not None and abs(number - (i + 1)) <= 30:
            printed[i] = number

        chapter_matches = re.findall(r'Глава\s+[IVX\d]+[^\n]*', txt, re.IGNORECASE)
        if chapter_matches:
            current_chapter = _clean_chapter(chapter_matches[-1])

        para_matches = re.findall(r'§\s*\d+(?:[.-]\d+)?', txt)
        if para_matches:
            current_paragraph = re.sub(r'\s+', ' ', para_matches[-1])

        pages.append((i, txt, current_chapter, current_paragraph))

    offset = _page_offset(printed)

    chunks = []
    CHUNK_SIZE = 800
    OVERLAP = 150

    for i, txt, chapter, paragraph in pages:
        number = printed.get(i)
        if number is None:
            number = i + 1 + offset
        if number < 1:
            number = i + 1

        text = txt.strip()
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            chunk_text = text[start:end]
            if chunk_text.strip():
                chunks.append({
                    "text": chunk_text,
                    "page": number,
                    "chapter": chapter,
                    "paragraph": paragraph,
                })
            start += CHUNK_SIZE - OVERLAP

    return chunks

def _parse_docx(content: bytes) -> list[dict]:
    chunks = []
    document = docx.Document(io.BytesIO(content))
    for para in document.paragraphs:
        if para.text.strip():
            chunks.append({"text": para.text.strip(), "page": 1})
    return chunks
