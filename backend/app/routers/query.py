from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class QueryRequest(BaseModel):
    text: str
    user_id: str
    language: str | None = None


class QueryResponse(BaseModel):
    answer: str
    confidence: str
    language: str


@router.post("/", response_model=QueryResponse)
def handle_query(req: QueryRequest):
    # TODO: call app.services.intent_extraction -> app.services.data_router -> app.services.response_composer
    return QueryResponse(answer="stub response", confidence="low", language=req.language or "en")
