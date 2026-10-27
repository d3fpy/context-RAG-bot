import uuid

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ApiException
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchText,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    TextIndexParams,
    VectorParams,
)

from app.config import settings

try:
    from qdrant_client.models import TokenizerType as _Tokenizer
except ImportError:
    from qdrant_client.models import Tokenizers as _Tokenizer

_client: QdrantClient | None = None

WORD_SCAN_LIMIT = 50
STEM_LEN = 8


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        _ensure_collection(_client)
        _ensure_indexes(_client)
    return _client


def _ensure_collection(client: QdrantClient):
    if client.collection_exists(settings.COLLECTION_NAME):
        return
    client.create_collection(
        collection_name=settings.COLLECTION_NAME,
        vectors_config=VectorParams(
            size=settings.VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )
    print(f"[qdrant] создана коллекция: {settings.COLLECTION_NAME}")


def _ensure_indexes(client: QdrantClient):
    name = settings.COLLECTION_NAME

    for field in ("class_name", "subject"):
        _safe_index(client, name, field, PayloadSchemaType.KEYWORD)
    for field in ("page", "document_id"):
        _safe_index(client, name, field, PayloadSchemaType.INTEGER)

    _safe_index(
        client, name, "text",
        TextIndexParams(
            type="text",
            tokenizer=_Tokenizer.PREFIX,
            lowercase=True,
            min_token_len=3,
        ),
    )


def _safe_index(client: QdrantClient, collection: str, field: str, schema):
    try:
        client.create_payload_index(
            collection_name=collection,
            field_name=field,
            field_schema=schema,
            wait=True,
        )
    except (ApiException, ValueError) as e:
        print(f"[qdrant] индекс {field} не создан:", e)


def upsert_chunks(chunks: list[dict], document_id: int) -> list[str]:
    client = get_client()
    points = []
    ids = []

    for ch in chunks:
        pid = str(uuid.uuid4())
        ids.append(pid)
        points.append(
            PointStruct(
                id=pid,
                vector=ch["vector"],
                payload={
                    "text": ch["text"],
                    "page": ch["page"],
                    "document_id": document_id,
                    "class_name": ch["class_name"],
                    "subject": ch["subject"],
                    "chapter": ch.get("chapter", ""),
                    "paragraph": ch.get("paragraph", ""),
                    "textbook": ch.get("textbook", ""),
                },
            )
        )

    client.upsert(collection_name=settings.COLLECTION_NAME, points=points)
    return ids


def _filter(class_name: str, subject: str) -> Filter:
    return Filter(
        must=[
            FieldCondition(key="class_name", match=MatchValue(value=class_name)),
            FieldCondition(key="subject", match=MatchValue(value=subject)),
        ]
    )


def search(query_vector: list[float], class_name: str, subject: str, top_k: int = 3):
    client = get_client()

    response = client.query_points(
        collection_name=settings.COLLECTION_NAME,
        query=query_vector,
        query_filter=_filter(class_name, subject),
        limit=top_k,
    )
    return response.points


def _stems(words: list[str]) -> list[str]:
    stems: list[str] = []
    for word in words:
        short = word[:STEM_LEN]
        for value in (word, short):
            if len(value) >= 3 and value not in stems:
                stems.append(value)
    return stems


def search_by_words(words: list[str], class_name: str, subject: str, top_k: int = 3):
    client = get_client()

    flt = Filter(
        must=_filter(class_name, subject).must,
        should=[
            FieldCondition(key="text", match=MatchText(text=stem))
            for stem in _stems(words)
        ],
    )

    try:
        points, _ = client.scroll(
            collection_name=settings.COLLECTION_NAME,
            scroll_filter=flt,
            limit=WORD_SCAN_LIMIT,
            with_payload=True,
        )
    except (ApiException, ValueError) as e:
        print("[qdrant] полнотекстовый поиск недоступен, сканируем:", e)
        points = _scan_by_words(client, class_name, subject)

    scored = []
    for p in points:
        text = (p.payload or {}).get("text", "").lower()
        score = sum(text.count(word) for word in words)
        if score > 0:
            scored.append((score, p))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [p for _, p in scored[:top_k]]


def _scan_by_words(client: QdrantClient, class_name: str, subject: str):
    points, _ = client.scroll(
        collection_name=settings.COLLECTION_NAME,
        scroll_filter=_filter(class_name, subject),
        limit=500,
        with_payload=True,
    )
    return points


def get_by_page(class_name: str, subject: str, page: int):
    client = get_client()

    flt = Filter(
        must=_filter(class_name, subject).must
        + [FieldCondition(key="page", match=MatchValue(value=page))]
    )

    points, _ = client.scroll(
        collection_name=settings.COLLECTION_NAME,
        scroll_filter=flt,
        limit=20,
        with_payload=True,
    )
    return points


def delete_by_document(document_id: int):
    client = get_client()

    flt = Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
    client.delete(
        collection_name=settings.COLLECTION_NAME,
        points_selector=FilterSelector(filter=flt),
    )


def delete_by_filter(class_name: str, subject: str):
    client = get_client()

    client.delete(
        collection_name=settings.COLLECTION_NAME,
        points_selector=FilterSelector(filter=_filter(class_name, subject)),
    )
