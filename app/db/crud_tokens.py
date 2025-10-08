# app/db/crud_tokens.py
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.db.models import User, LinkedInToken
from app.db import token_crypto

def upsert_user(db: Session, email: str | None) -> User:
    # Create a new user row (email optional for LinkedIn-only auth)
    u = User(email=email)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u

def set_user_member_id(db: Session, user_id: int, member_id: str) -> None:
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return
    u.member_id = member_id
    db.add(u)
    db.commit()

def set_user_person_id(db: Session, user_id: int, person_id: str) -> None:
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        return
    u.person_id = person_id
    db.add(u)
    db.commit()

def save_linkedin_token(
    db: Session,
    user_id: int,
    access_token_encrypted: str,
    expires_in: int,
    refresh_token_encrypted: str | None = None,
    id_token_encrypted: str | None = None,
) -> LinkedInToken:
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    row = LinkedInToken(
        user_id=user_id,
        access_token_encrypted=access_token_encrypted,
        refresh_token_encrypted=refresh_token_encrypted,
        id_token_encrypted=id_token_encrypted,     # ← store it
        expires_at=expires_at,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def get_latest_token(db: Session, user_id: int) -> LinkedInToken | None:
    return (
        db.query(LinkedInToken)
        .filter(LinkedInToken.user_id == user_id)
        .order_by(LinkedInToken.id.desc())
        .first()
    )

def is_token_expiring(tok: LinkedInToken, seconds: int = 300) -> bool:
    return bool(tok.expires_at and (tok.expires_at - datetime.utcnow()).total_seconds() < seconds)

def get_latest_refresh_token(db: Session, user_id: int) -> str | None:
    tok = get_latest_token(db, user_id)
    return tok.refresh_token_encrypted if tok else None   # encrypted (your caller decrypts)

def update_access_token_only(db: Session, user_id: int, new_access_token: str, expires_in: int) -> None:
    last = get_latest_token(db, user_id)
    if not last:
        return
    last.access_token_encrypted = token_crypto.encrypt_token(new_access_token)
    last.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    db.add(last)
    db.commit()
