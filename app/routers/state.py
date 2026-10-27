from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import UserState

router = APIRouter(prefix="/api", tags=["state"])

COLUMNS = ("role", "step", "class_name", "subject")


def _apply(row: UserState, data: dict, partial: bool = False):
    for field in COLUMNS:
        if partial and field not in data:
            continue
        setattr(row, field, data.get(field))
    if not partial or "history" in data:
        row.history = data.get("history") or []
    row.extra = {k: v for k, v in data.items() if k not in COLUMNS and k != "history"}


def _as_dict(row: UserState) -> dict:
    data = dict(row.extra or {})
    for field in COLUMNS:
        value = getattr(row, field)
        if value is not None:
            data[field] = value
    if row.history:
        data["history"] = row.history
    return data


@router.get("/state")
def all_states(db: Annotated[Session, Depends(get_db)]):
    rows = db.query(UserState).all()
    return {row.user_id: _as_dict(row) for row in rows}


@router.put("/state")
def replace_states(states: dict[str, dict], db: Annotated[Session, Depends(get_db)]):
    existing = {row.user_id: row for row in db.query(UserState).all()}
    saved = 0

    for raw_id, data in states.items():
        try:
            user_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        if not isinstance(data, dict):
            continue

        row = existing.get(user_id)
        if row is None:
            row = UserState(user_id=user_id)
            db.add(row)
            existing[user_id] = row
        _apply(row, data)
        saved += 1

    db.commit()
    return {"ok": True, "users": saved}


@router.get("/state/{user_id}")
def get_state(user_id: int, db: Annotated[Session, Depends(get_db)]):
    row = db.query(UserState).filter(UserState.user_id == user_id).first()
    return _as_dict(row) if row else {}


@router.post("/state/{user_id}")
def save_state(user_id: int, data: dict, db: Annotated[Session, Depends(get_db)]):
    row = db.query(UserState).filter(UserState.user_id == user_id).first()
    if not row:
        row = UserState(user_id=user_id)
        db.add(row)
    _apply(row, data, partial=True)
    db.commit()
    return {"ok": True}


@router.delete("/state/{user_id}")
def delete_state(user_id: int, db: Annotated[Session, Depends(get_db)]):
    row = db.query(UserState).filter(UserState.user_id == user_id).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}
