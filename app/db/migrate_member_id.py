import sqlite3
import os

db_path = os.getenv("DB_PATH", "app.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check if member_id column exists
c.execute("PRAGMA table_info(users)")
columns = [row[1] for row in c.fetchall()]
if "member_id" not in columns:
    c.execute("ALTER TABLE users ADD COLUMN member_id TEXT")
    print("Added member_id column to users table.")
else:
    print("member_id column already exists.")
conn.commit()
conn.close()
