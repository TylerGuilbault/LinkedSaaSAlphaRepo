from fastapi import APIRouter, Depends
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.services.summarize import summarize_text
from app.services.rewrite import rewrite_linkedin
from app.deps import get_db
from app.db import crud

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

class PipelineIn(BaseModel):
    title: str
    url: HttpUrl
    text: str
    tone: Optional[str] = "professional"
    source: Optional[str] = None
    published: Optional[str] = None
    max_length: Optional[int] = 160
    min_length: Optional[int] = 60

@router.post("/post_and_save")
def post_and_save(body: PipelineIn, db: Session = Depends(get_db)) -> Dict[str, Any]:
    # summarize
    summary = summarize_text(body.text, max_length=body.max_length or 160, min_length=body.min_length or 60)
    # rewrite
    post = rewrite_linkedin(summary, tone=body.tone or "professional")
    # save article (idempotent by url)
    crud.get_article_by_url(db, str(body.url)) or crud.create_article(db, {
        "title": body.title, "summary": summary, "url": str(body.url),
        "published": body.published, "source": body.source,
    })
    # save post
    p = crud.create_post(db, draft=post, tone=body.tone or "professional", article_url=str(body.url))
    return {"summary": summary, "post": post, "post_id": p.id}
