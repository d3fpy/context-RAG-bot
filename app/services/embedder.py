import os

from fastembed import TextEmbedding

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".cache", "fastembed")

_model = None


def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        print("[embedder] загружаем модель", MODEL_NAME)
        _model = TextEmbedding(MODEL_NAME, cache_dir=CACHE_DIR)
    return _model


def embed(text: str) -> list[float]:
    return list(next(_get_model().embed([text])))


def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return [list(v) for v in _get_model().embed(texts)]
