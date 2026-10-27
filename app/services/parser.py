import io
import re
from collections import Counter

import docx
import pypdf

_PAGE_LINE_RE = re.compile(r"^[^\w]{0,6}(\d{1,4})[^\w]{0,6}$")

PAGE_TOLERANCE = 40


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


def _printed_number(txt: str, index: int) -> int | None:
    lines = [line.strip() for line in txt.splitlines() if line.strip()]
    if not lines:
        return None

    seen = set()
    for line in lines[:3] + lines[-3:]:
        if line in seen:
            continue
        seen.add(line)
        match = _PAGE_LINE_RE.match(line)
        if not match:
            continue
        number = int(match.group(1))
        if 1 <= number <= 2000 and abs(number - (index + 1)) <= PAGE_TOLERANCE:
            return number
    return None


def _page_offset(printed: dict[int, int]) -> int:
    if len(printed) < 5:
        return 0
    diffs = [value - (idx + 1) for idx, value in printed.items()]
    common, count = Counter(diffs).most_common(1)[0]
    return common if count >= len(diffs) * 0.5 else 0


def _page_number(index: int, printed: dict[int, int], offset: int) -> int:
    expected = index + 1 + offset
    number = printed.get(index)
    if number is None or abs(number - expected) > 3:
        number = expected
    if number < 1:
        number = index + 1
    return number


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

        number = _printed_number(txt, i)
        if number is not None:
            printed[i] = number

        chapter_matches = re.findall(r'Глава\s+[IVX\d]+[^\n]*', txt, re.IGNORECASE)
        if chapter_matches:
            current_chapter = _clean_chapter(chapter_matches[-1])

        para_matches = re.findall(r'§\s*\d+(?:[.-]\d+)?', txt)
        if para_matches:
            current_paragraph = re.sub(r'\s+', ' ', para_matches[-1])

        pages.append((i, txt, current_chapter, current_paragraph))

    if not pages:
        raise ValueError(
            "В PDF нет текстового слоя — похоже, это сканы. Пришлите PDF с текстом или DOCX."
        )

    offset = _page_offset(printed)

    chunks = []
    CHUNK_SIZE = 800
    OVERLAP = 150

    for i, txt, chapter, paragraph in pages:
        number = _page_number(i, printed, offset)

        text = txt.strip()
        start = 0
        while start < len(text):
            end = min(start + CHUNK_SIZE, len(text))
            if end < len(text):
                left = start + CHUNK_SIZE // 2
                cut = max(text.rfind(" ", left, end), text.rfind("\n", left, end))
                if cut != -1:
                    end = cut
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "page": number,
                    "chapter": chapter,
                    "paragraph": paragraph,
                })
            if end >= len(text):
                break
            start = max(end - OVERLAP, start + 1)

    return chunks


def _parse_docx(content: bytes) -> list[dict]:
    chunks = []
    document = docx.Document(io.BytesIO(content))
    for para in document.paragraphs:
        if para.text.strip():
            chunks.append({"text": para.text.strip(), "page": 1})
    return chunks
