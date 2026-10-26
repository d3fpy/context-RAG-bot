import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from app.config import settings

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        _ensure_collection(_client)
    return _client


def _ensure_collection(client: QdrantClient):
    if not client.collection_exists(settings.COLLECTION_NAME):
        client.create_collection(
            collection_name=settings.COLLECTION_NAME,
            vectors_config=VectorParams(
                size=settings.VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        print(f"[qdrant] создана коллекция: {settings.COLLECTION_NAME}")


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

def search(query_vector: list[float], class_name: str, subject: str, top_k: int = 3):
    client = get_client()

    flt = Filter(
        must=[
            FieldCondition(key="class_name", match=MatchValue(value=class_name)),
            FieldCondition(key="subject", match=MatchValue(value=subject)),
        ]
    )

    response = client.query_points(
        collection_name=settings.COLLECTION_NAME,
        query=query_vector,
        query_filter=flt,
        limit=top_k
    )
    return response.points


def search_by_words(words: list[str], class_name: str, subject: str, top_k: int = 3):
    client = get_client()

    flt = Filter(
        must=[
            FieldCondition(key="class_name", match=MatchValue(value=class_name)),
            FieldCondition(key="subject", match=MatchValue(value=subject)),
        ]
    )

    points, _ = client.scroll(
        collection_name=settings.COLLECTION_NAME,
        scroll_filter=flt,
        limit=100, 
        with_payload=True,
    )

    def score(p):
        text = p.payload["text"].lower()
        return sum(text.count(w) for w in words)

    points = sorted(points, key=score, reverse=True)
    return points[:top_k]


def get_by_page(class_name: str, subject: str, page: int):
    client = get_client()

    flt = Filter(
        must=[
            FieldCondition(key="class_name", match=MatchValue(value=class_name)),
            FieldCondition(key="subject", match=MatchValue(value=subject)),
            FieldCondition(key="page", match=MatchValue(value=page)),
        ]
    )

    points, _ = client.scroll(
        collection_name=settings.COLLECTION_NAME,
        scroll_filter=flt,
        limit=5,
        with_payload=True,
    )
    return points


def delete_by_filter(class_name: str, subject: str):
    client = get_client()

    flt = Filter(
        must=[
            FieldCondition(key="class_name", match=MatchValue(value=class_name)),
            FieldCondition(key="subject", match=MatchValue(value=subject)),
        ]
    )

    client.delete(
        collection_name=settings.COLLECTION_NAME,
        points_selector=FilterSelector(filter=flt),
    )