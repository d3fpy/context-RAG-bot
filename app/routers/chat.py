from fastapi import APIRouter

from app.schemas import AskRequest, AskResponse, PageRequest
from app.services import qdrant_client as qdrant
from app.services.embedder import embed
from app.services.llm import generate_answer

router = APIRouter(prefix="/api", tags=["chat"])

STOP_WORDS = {
    "такое", "такой", "такая", "чтобы", "который", "которые",
    "нужно", "надо", "значит", "определение",
}

EXCERPT_LIMIT = 700
EXCERPT_OFFSET = 400
VECTOR_K = 6
MAX_PAYLOADS = 4
WORD_SEARCH_K = 3

REFERENCE_MARKERS = ("на странице", "см. страницу", "смотрите", "см. с.")


def _keywords(question: str) -> list[str]:
    words = [w.strip('.,!?;:()«»"-').lower() for w in question.split()]
    return [w for w in words if len(w) >= 5 and w not in STOP_WORDS]


def _excerpt(text: str, words: list[str], limit: int = EXCERPT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    pos = -1
    for w in words:
        idx = text.lower().find(w)
        if idx != -1:
            pos = idx
            break
    start = max(0, (pos if pos != -1 else 0) - EXCERPT_OFFSET)
    return text[start:start + limit]


def _is_reference(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in REFERENCE_MARKERS)


def _best_page(payloads: list[dict], words: list[str]) -> int:
    if not words:
        return payloads[0]["page"]

    candidates = [p for p in payloads if not _is_reference(p["text"])] or payloads
    best_page = candidates[0]["page"]
    best_score = -1

    for p in candidates:
        score = sum(p["text"].lower().count(w) for w in words)
        if score > best_score:
            best_score = score
            best_page = p["page"]

    return best_page


def _dedupe(payloads: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for p in payloads:
        key = (p.get("page"), p.get("text"))
        if key in seen:
            continue
        seen.add(key)
        result.append(p)
    return result


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    query_vec = embed(req.question)
    words = _keywords(req.question)

    hits = qdrant.search(
        query_vector=query_vec,
        class_name=req.class_name,
        subject=req.subject,
        top_k=VECTOR_K,
    )
    payloads = [h.payload for h in hits]

    if words:
        extra = [
            p.payload
            for p in qdrant.search_by_words(words, req.class_name, req.subject, top_k=WORD_SEARCH_K)
        ]
        payloads = extra + payloads

    payloads = _dedupe(payloads)[:MAX_PAYLOADS]

    if not payloads:
        return AskResponse(
            answer="В материалах вашего класса я не нашёл ответа на этот вопрос.",
            page=0,
        )

    context = "\n\n---\n\n".join(
        f"[Фрагмент {i + 1}, страница {p['page']}]\n{_excerpt(p['text'], words)}"
        for i, p in enumerate(payloads)
    )

    answer, page = generate_answer(
        context,
        req.question,
        payloads[0]["page"],
        req.history,
        req.detailed,
    )

    pages = {p["page"] for p in payloads}
    if page not in pages:
        page = _best_page(payloads, words)

    source = next((p for p in payloads if p["page"] == page), payloads[0])
    top_text = source["text"]

    return AskResponse(
        answer=answer,
        page=page,
        source_text=top_text[:200] + ("..." if len(top_text) > 200 else ""),
        textbook=source.get("textbook", ""),
        chapter=source.get("chapter", ""),
        paragraph=source.get("paragraph", ""),
    )


@router.post("/page", response_model=AskResponse)
def page_summary(req: PageRequest) -> AskResponse:
    hits = qdrant.get_by_page(req.class_name, req.subject, req.page)

    if not hits:
        return AskResponse(
            answer=f"Страница {req.page} в материалах этого класса не найдена.",
            page=req.page,
        )

    top = hits[0].payload
    context = "\n\n---\n\n".join(h.payload["text"] for h in hits)
    answer, _ = generate_answer(
        context,
        "Сделай краткий конспект этой страницы: главные определения, правила и формулы.",
        req.page,
    )

    return AskResponse(
        answer=answer,
        page=req.page,
        textbook=top.get("textbook", ""),
        chapter=top.get("chapter", ""),
        paragraph=top.get("paragraph", ""),
    )
