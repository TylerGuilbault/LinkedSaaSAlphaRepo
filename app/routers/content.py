from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.summarize import summarize_text
from app.services.rewrite import rewrite_linkedin

router = APIRouter(prefix="/generate", tags=["generate"])

class SummaryIn(BaseModel):
    text: str
    max_length: Optional[int] = 180
    min_length: Optional[int] = 60

class RewriteIn(BaseModel):
    text: str
    tone: Optional[str] = "professional"

@router.post("/summary")
def generate_summary(body: SummaryIn):
    summary = summarize_text(body.text, max_length=body.max_length, min_length=body.min_length)
    return {"summary": summary}

@router.post("/post")
def generate_linkedin_post(body: RewriteIn):
    post = rewrite_linkedin(body.text, tone=body.tone or "professional")
    return {"post": post}
