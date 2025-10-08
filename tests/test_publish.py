import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.routers.linkedin_publish import router as publish_router
from app.routers.auth_linkedin import router as auth_router
from app.main import app

client = TestClient(app)

# These tests are integration-light: they patch functions to simulate DB and LinkedIn API

def test_publish_missing_token(monkeypatch):
    # Simulate no token on file by mocking get_latest_token
    from app.db import crud_tokens

    def fake_get_latest_token(db, user_id):
        return None

    monkeypatch.setattr(crud_tokens, "get_latest_token", fake_get_latest_token)

    resp = client.post("/linkedin/post", json={"user_id": 9999, "text": "hi"})
    assert resp.status_code == 400
    assert "No LinkedIn token" in resp.json().get("detail")


def test_publish_derives_member_id_and_posts(monkeypatch):
    # Simulate token present and user without member_id; ensure userinfo_sub is called and post_text used
    from app.db import crud_tokens, models
    from app.services import linkedin_api

    class FakeToken:
        access_token_encrypted = "encrypted"
        refresh_token_encrypted = None
        expires_at = None

    def fake_get_latest_token(db, user_id):
        return FakeToken()

    def fake_decrypt(enc):
        return "plain-token"

    def fake_userinfo_sub(access_token):
        return "openid-sub-123"

    posted = {}

    def fake_post_text(access_token, author_urn, text):
        posted['author'] = author_urn
        posted['text'] = text
        return True, type('R', (), {'text': 'ok'})()

    # mock crud_tokens.get_latest_token and token decryption
    monkeypatch.setattr(crud_tokens, "get_latest_token", fake_get_latest_token)
    monkeypatch.setattr('app.db.token_crypto.decrypt_token', lambda enc: 'plain-token')
    monkeypatch.setattr(linkedin_api, "userinfo_sub", fake_userinfo_sub)
    monkeypatch.setattr(linkedin_api, "post_text", fake_post_text)

    # Ensure user exists without member_id
    # We'll use the real DB to create a user
    # create a user via the upsert_user helper using a direct DB session
    from app.db.base import SessionLocal
    from app.db import crud_tokens as ct
    db = SessionLocal()
    try:
        u = ct.upsert_user(db, email=None)
        user_id = u.id
    finally:
        db.close()

    resp = client.post("/linkedin/post", json={"user_id": user_id, "text": "hello"})
    # after call, our fake_post_text should have been invoked
    assert resp.status_code == 200
    assert posted['author'].startswith('urn:li:member:openid-sub-123')
    assert posted['text'] == 'hello'
