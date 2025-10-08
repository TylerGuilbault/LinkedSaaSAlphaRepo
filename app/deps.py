from typing import Generator
from app.db.base import SessionLocal, engine, Base
from app.db import models
from app.db.migrate import migrate

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    migrate(engine)

def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
