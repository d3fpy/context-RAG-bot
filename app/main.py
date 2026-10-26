from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import chat, state, upload

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Контекст API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(state.router)

