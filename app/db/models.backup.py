from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func
from app.db.base import Base

class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512))
    summary = Column(Text)
    url = Column(String(1024), unique=True, index=True)
    published = Column(String(64), nullable=True)  # ISO datetime string
    source = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True, index=True)
    article_url = Column(String(1024), index=True)  # optional link back
    draft = Column(Text)    # the LinkedIn-ready post text
    tone = Column(String(64), default="professional")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # new fields for scheduling/state
    sent_at = Column(DateTime(timezone=True), nullable=True)
    platform_status = Column(String(128), nullable=True)  # e.g., 'queued','posted','failed:...'
