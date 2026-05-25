from fastapi import APIRouter, Query

from app.schemas import WikiChunk
from app.services.wiki_service import get_indexed_wiki_chunks, reload_wiki_chunks, search_indexed_wiki

router = APIRouter()


@router.get("/wiki/chunks", response_model=list[WikiChunk])
async def list_wiki_chunks() -> list[WikiChunk]:
    return get_indexed_wiki_chunks()


@router.get("/wiki/search", response_model=list[WikiChunk])
async def search_wiki(q: str = Query(default=""), limit: int = Query(default=5, ge=1, le=20)) -> list[WikiChunk]:
    return search_indexed_wiki(q, limit=limit)


@router.post("/wiki/reload", response_model=list[WikiChunk])
async def reload_wiki() -> list[WikiChunk]:
    return reload_wiki_chunks()
