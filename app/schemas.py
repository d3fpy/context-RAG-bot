from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    class_name: str
    subject: str
    history: list[str] = []
    detailed: bool = False

class PageRequest(BaseModel):
    class_name: str
    subject: str
    page: int

class AskResponse(BaseModel):
    answer: str
    page: int
    source_text: str = ""
    textbook: str = ""
    chapter: str = ""
    paragraph: str = ""

class UploadResponse(BaseModel):
    ok: bool
    document_id: int
    chunks: int
    message: str = ""

class MaterialItem(BaseModel):
    class_name: str
    subject: str

class DeleteResponse(BaseModel):
    ok: bool
    deleted: int = 0
    message: str = ""