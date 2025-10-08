from sqlalchemy import text
from sqlalchemy.engine import Engine

def column_exists(engine: Engine, table: str, column: str) -> bool:
    with engine.connect() as conn:
        res = conn.execute(text(f"PRAGMA table_info({table})"))
        cols = [row[1] for row in res.fetchall()]
        return column in cols

def migrate(engine: Engine) -> None:
    # add sent_at/platform_status to posts if they don't exist (SQLite only)
    with engine.begin() as conn:
        if not column_exists(engine, "posts", "sent_at"):
            conn.execute(text("ALTER TABLE posts ADD COLUMN sent_at TEXT"))
        if not column_exists(engine, "posts", "platform_status"):
            conn.execute(text("ALTER TABLE posts ADD COLUMN platform_status TEXT"))
