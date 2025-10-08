from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from app.db import models

def get_article_by_url(db: Session, url: str) -> Optional[models.Article]:
    return db.query(models.Article).filter(models.Article.url == url).first()

def create_article(db: Session, data: Dict[str, Any]) -> models.Article:
    obj = models.Article(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def list_articles(db: Session, limit: int = 20) -> List[models.Article]:
    return db.query(models.Article).order_by(models.Article.id.desc()).limit(limit).all()

def create_post(db: Session, draft: str, tone: str = "professional", article_url: Optional[str] = None) -> models.Post:
    obj = models.Post(draft=draft, tone=tone, article_url=article_url)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def list_posts(db: Session, limit: int = 20) -> List[models.Post]:
    return db.query(models.Post).order_by(models.Post.id.desc()).limit(limit).all()
