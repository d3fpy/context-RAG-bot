from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from qdrant_client.http.exceptions import ApiException
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chunk, Document
from app.schemas import DeleteResponse, MaterialItem, UploadResponse
from app.services import qdrant_client as qdrant
from app.services.embedder import embed_batch
from app.services.parser import parse_file

router = APIRouter(prefix="/api", tags=["materials"])


@router.get("/materials", response_model=list[MaterialItem])
def list_materials(db: Annotated[Session, Depends(get_db)]):
    rows = db.query(Document.class_name, Document.subject).distinct().all()
    return [MaterialItem(class_name=row.class_name, subject=row.subject) for row in rows]


@router.get("/stats")
def get_stats(db: Annotated[Session, Depends(get_db)]):
    total_docs = db.query(func.count(Document.id)).scalar() or 0
    total_chunks = db.query(func.count(Chunk.id)).scalar() or 0

    doc_rows = (
        db.query(Document.class_name, Document.subject, func.count(Document.id))
        .group_by(Document.class_name, Document.subject)
        .all()
    )
    chunk_rows = (
        db.query(Document.class_name, Document.subject, func.count(Chunk.id))
        .join(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.class_name, Document.subject)
        .all()
    )
    chunk_map = {(c, s): n for c, s, n in chunk_rows}

    materials = [
        {
            "class_name": c,
            "subject": s,
            "documents": n,
            "chunks": chunk_map.get((c, s), 0),
        }
        for c, s, n in doc_rows
    ]
    return {"documents": total_docs, "chunks": total_chunks, "materials": materials}


@router.delete("/materials", response_model=DeleteResponse)
def delete_materials(class_name: str, subject: str, db: Annotated[Session, Depends(get_db)]):
    docs = db.query(Document).filter(
        Document.class_name == class_name,
        Document.subject == subject
    ).all()

    if not docs:
        return DeleteResponse(ok=False, message="Материалы не найдены")

    deleted = sum(len(d.chunks) for d in docs)

    try:
        qdrant.delete_by_filter(class_name, subject)
        for d in docs:
            db.delete(d)
        db.commit()
    except (ApiException, SQLAlchemyError, ValueError) as e:
        print("ошибка удаления", e)
        db.rollback()
        return DeleteResponse(ok=False, message="Не получилось удалить материалы")

    return DeleteResponse(ok=True, deleted=deleted,
                          message=f"Материалы «{class_name} {subject}» удалены. Фрагментов: {deleted}")


@router.post("/upload", response_model=UploadResponse)
def upload_material(
    file: Annotated[UploadFile, File()],
    class_name: Annotated[str, Form()],
    subject: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
    textbook_name: Annotated[str, Form()] = "",
    topic: Annotated[str, Form()] = "",
):
    raw = file.file.read()

    try:
        chunks = parse_file(raw, file.filename or "")
    except ValueError as e:
        return UploadResponse(ok=False, document_id=0, chunks=0, message=str(e))

    if not chunks:
        return UploadResponse(ok=False, document_id=0, chunks=0,
                              message="Не удалось извлечь текст")

    doc = Document(filename=file.filename or "", class_name=class_name,
                   subject=subject, topic=topic)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        vectors = embed_batch([c["text"] for c in chunks])

        payload_chunks = [
            {
                "text": c["text"],
                "page": c["page"],
                "vector": v,
                "class_name": class_name,
                "subject": subject,
                "chapter": c.get("chapter", ""),
                "paragraph": c.get("paragraph", ""),
                "textbook": textbook_name,
                "topic": topic
            }
            for c, v in zip(chunks, vectors)
        ]

        qdrant_ids = qdrant.upsert_chunks(payload_chunks, document_id=doc.id)

        for c, qid in zip(chunks, qdrant_ids):
            db.add(Chunk(
                document_id=doc.id,
                page=c["page"],
                text=c["text"],
                qdrant_id=qid
            ))
        db.commit()
    except (ApiException, SQLAlchemyError, RuntimeError, ValueError, OSError) as e:
        print("Ошибка загрузки", e)
        try:
            qdrant.delete_by_document(doc.id)
        except (ApiException, ValueError) as qdrant_error:
            print("не удалось почистить Qdrant", qdrant_error)
        db.rollback()
        db.delete(doc)
        db.commit()
        return UploadResponse(ok=False, document_id=0, chunks=0,
                              message="Не удалось обработать файл")

    return UploadResponse(
        ok=True,
        document_id=doc.id,
        chunks=len(chunks),
        message=f"Загружено {len(chunks)} фрагментов"
    )
