import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DB_URL = os.getenv("DB_URL", "postgresql://postgres:postgres@localhost:5432/context")

    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    COLLECTION_NAME = os.getenv("COLLECTION_NAME", "materials")

    VECTOR_SIZE = 384


settings = Settings()