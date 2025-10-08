
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, ANY
from app.main import app

client = TestClient(app)

@patch("app.db.crud_tokens.get_latest_refresh_token")
@patch("app.services.linkedin_api.exchange_refresh_for_token")
@patch("app.db.crud_tokens.update_access_token_only")
def test_refresh_happy_path(mock_update, mock_exchange, mock_get_refresh):
    mock_get_refresh.return_value = "enc_refresh"
    mock_exchange.return_value = {"access_token": "new_access", "expires_in": 3600}
    mock_update.return_value = MagicMock()
    resp = client.post("/auth/linkedin/refresh", json={"user_id": 1})
    assert resp.status_code == 200
    mock_update.assert_called_with(ANY, 1, "new_access", 3600)

@patch("app.db.crud_tokens.get_latest_token")
@patch("app.db.models.User")
def test_post_uses_stored_member_id_when_missing_in_body(mock_user, mock_get_token):
    mock_token = MagicMock()
    mock_token.access_token_encrypted = "enc"
    mock_user_obj = MagicMock()
    mock_user_obj.member_id = "stored_id"
    mock_get_token.return_value = mock_token
    with patch("app.db.token_crypto.decrypt_token", return_value="access"), \
         patch("app.services.linkedin_api.post_text", return_value=(True, "ref")), \
         patch("app.services.linkedin_api.userinfo_sub", return_value="stored_id"), \
         patch("sqlalchemy.orm.Session.query") as mock_query:
        mock_query.return_value.filter.return_value.first.return_value = mock_user_obj
        resp = client.post("/linkedin/post", json={"user_id": 1, "text": "hi"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "posted"
        assert resp.json()["ref"] == "ref"

@patch("app.db.crud_tokens.get_latest_token")
@patch("app.db.crud_tokens.is_token_expiring", return_value=True)
@patch("app.db.crud_tokens.get_latest_refresh_token")
@patch("app.services.linkedin_api.exchange_refresh_for_token")
@patch("app.db.crud_tokens.update_access_token_only")
def test_post_triggers_refresh_when_expired(mock_update, mock_exchange, mock_get_refresh, mock_expiring, mock_get_token):
    mock_token = MagicMock()
    mock_token.access_token_encrypted = "enc"
    mock_get_token.return_value = mock_token
    mock_get_refresh.return_value = "enc_refresh"
    mock_exchange.return_value = {"access_token": "new_access", "expires_in": 3600}
    mock_update.return_value = MagicMock()
    with patch("app.db.token_crypto.decrypt_token", return_value="access"), \
        patch("app.services.linkedin_api.post_text", return_value=(True, "ref")), \
        patch("app.services.linkedin_api.userinfo_sub", return_value="stored_id"), \
        patch("app.db.models.User") as mock_user:
        mock_user_obj = MagicMock()
        mock_user_obj.member_id = "stored_id"
        mock_user.return_value = mock_user_obj
        resp = client.post("/linkedin/post", json={"user_id": 1, "text": "hi", "member_id": None})
        assert resp.status_code == 200
        assert resp.json()["status"] == "posted"
        assert resp.json()["ref"] == "ref"
        mock_update.assert_called_with(ANY, 1, "new_access", 3600)
