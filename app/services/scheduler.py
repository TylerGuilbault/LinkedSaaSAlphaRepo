from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.base import SessionLocal
from app.db import models
from app.services.linkedin_client import post_text_to_linkedin

def pick_next_draft(db: Session) -> models.Post | None:
    return (
        db.query(models.Post)
        .filter(models.Post.sent_at.is_(None))
        .order_by(models.Post.id.desc())
        .first()
    )

def run_once() -> dict:
    # each job run gets its own session
    db = SessionLocal()
    try:
        post = pick_next_draft(db)
        if not post:
            return {"status": "no-drafts"}

        ok, ref = post_text_to_linkedin(None, post.draft)  # replace None with user token later
        if ok:
            post.sent_at = datetime.now(timezone.utc)
            post.platform_status = f"posted:{ref}"
            db.add(post); db.commit()
            return {"status": "posted", "post_id": post.id, "ref": ref}
        else:
            post.platform_status = f"failed:{ref}"
            db.add(post); db.commit()
            return {"status": "failed", "post_id": post.id, "error": ref}
    finally:
        db.close()
