# app/routers/auth_linkedin.py
import secrets
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.deps import get_db
from app.config import settings
import app.services.linkedin_api as linkedin_api
from app.db import crud_tokens
from app.db import token_crypto
from app.db.models import User

# NEW: decode helper
from app.auth.oidc import decode_linkedin_id_token
import anyio

router = APIRouter(prefix="/auth/linkedin", tags=["linkedin-auth"])
STATE_STORE: set[str] = set()

@router.get("/me")
def me():
    return {
        "status": "ok",
        "has_client_id": bool(settings.linkedin_client_id),
        "has_secret": bool(settings.linkedin_client_secret),
        "has_fernet": bool(settings.fernet_key),
        "redirect_uri": settings.linkedin_redirect_uri,
    }

@router.get("/login")
def login() -> RedirectResponse:
    if not settings.linkedin_client_id or not settings.linkedin_client_secret or not settings.fernet_key:
        raise HTTPException(500, "Missing LinkedIn or FERNET config in .env")
    state = secrets.token_urlsafe(24)
    STATE_STORE.add(state)
    # ensure OpenID (id_token) + posting
    scopes = "openid profile email w_member_social"
    url = linkedin_api.auth_url(state, scopes=scopes)
    return RedirectResponse(url)

@router.get("/callback")
def callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if error:
        if state in STATE_STORE:
            STATE_STORE.discard(state)
        return JSONResponse(
            status_code=400,
            content={"status": "error", "error": error, "error_description": error_description},
        )

    if not code or not state:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Missing ?code or ?state in callback"},
        )

    if state not in STATE_STORE:
        raise HTTPException(400, "Invalid state")
    STATE_STORE.discard(state)

    token_resp = linkedin_api.exchange_code_for_token(code)
    access_token = token_resp.get("access_token")
    refresh_token = token_resp.get("refresh_token")  # may be absent
    expires_in   = token_resp.get("expires_in", 3600)
    id_token     = token_resp.get("id_token")

    if not access_token:
        raise HTTPException(400, f"Token exchange failed: {token_resp}")

    # Derive member_id from id_token.sub (preferred)
    member_id = linkedin_api.extract_sub_from_id_token(id_token) if id_token else ""

    # Reuse existing user by member_id, else create one
    user = db.query(User).filter(User.member_id == member_id).first() if member_id else None
    if not user:
        user = crud_tokens.upsert_user(db, email=None)

    # Encrypt tokens
    access_token_enc  = token_crypto.encrypt_token(access_token)
    refresh_token_enc = token_crypto.encrypt_token(refresh_token) if refresh_token else None
    id_token_enc      = token_crypto.encrypt_token(id_token) if id_token else None

    # Persist latest token row (NOW includes id_token_encrypted)
    crud_tokens.save_linkedin_token(
        db=db,
        user_id=user.id,
        access_token_encrypted=access_token_enc,
        expires_in=expires_in,
        refresh_token_encrypted=refresh_token_enc,
        id_token_encrypted=id_token_enc,
    )

    # Persist member_id on users if we have one
    if member_id:
        try:
            if not user.member_id:
                crud_tokens.set_user_member_id(db, user.id, member_id)
        except Exception:
            print("Failed to persist member_id on user", flush=True)

    return {
        "status": "ok",
        "user_id": user.id,
        "expires_in": expires_in,
        "has_id_token": bool(id_token),
        "member_id": member_id or None,
    }

# Debug helper: show decoded id_token.sub instead of userinfo
@router.get("/debug/whoami")
def whoami(user_id: int = Query(...), db: Session = Depends(get_db)):
    tok = crud_tokens.get_latest_token(db, user_id=user_id)
    if not tok:
        return {"status": "no_token"}

    # Decrypt id_token if present
    token_sub = None
    if getattr(tok, "id_token_encrypted", None):
        try:
            id_token = token_crypto.decrypt_token(tok.id_token_encrypted)
            decoded = anyio.run(lambda: decode_linkedin_id_token(id_token))
            token_sub = decoded.get("sub")
        except Exception:
            token_sub = None

    user = db.query(User).filter(User.id == user_id).first()
    db_member_id = user.member_id if user else None
    db_person_id = user.person_id if user else None

    return {
        "status": "ok",
        "user_id": user_id,
        "openid_sub": token_sub,
        "person_id": db_person_id,
        "db_member_id": db_member_id,
        "author_person_urn": f"urn:li:person:{db_person_id}" if db_person_id else None,
        "author_member_urn": f"urn:li:member:{token_sub}" if token_sub else None,
        "match": bool(token_sub and db_member_id and token_sub == db_member_id),
    }
