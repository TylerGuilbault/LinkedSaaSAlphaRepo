from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Any, Dict
from sqlalchemy.orm import Session
from app.deps import get_db
from app.db import crud

router = APIRouter(prefix="/storage", tags=["storage"])

class ArticleIn(BaseModel):
    title: str
    summary: str
    url: HttpUrl
    published: Optional[str] = None
    source: Optional[str] = None

class PostIn(BaseModel):
    draft: str
    tone: Optional[str] = "professional"
    article_url: Optional[HttpUrl] = None

@router.post("/article")
def save_article(body: ArticleIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    existing = crud.get_article_by_url(db, str(body.url))
    if existing:
        return {"status": "exists", "id": existing.id}
    a = crud.create_article(db, {
        "title": body.title, "summary": body.summary, "url": str(body.url),
        "published": body.published, "source": body.source,
    })
    return {"status": "saved", "id": a.id}

@router.get("/articles")
def list_articles(limit: int = 20, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows = crud.list_articles(db, limit=limit)
    return [
        {"id": r.id, "title": r.title, "url": r.url, "published": r.published, "source": r.source, "summary": r.summary}
        for r in rows
    ]

@router.post("/post")
def save_post(body: PostIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    p = crud.create_post(db, draft=body.draft, tone=body.tone or "professional", article_url=str(body.article_url) if body.article_url else None)
    return {"status": "saved", "id": p.id}

@router.get("/posts")
def list_posts(limit: int = 20, db: Session = Depends(get_db)) -> List[Dict[str, Any]]:
    rows = crud.list_posts(db, limit=limit)
    return [
        {"id": r.id, "tone": r.tone, "article_url": r.article_url, "draft": r.draft, "created_at": str(r.created_at)}
        for r in rows
    ]
