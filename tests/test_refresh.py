
import sys
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# Ensure app is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.main import app

client = TestClient(app)

@patch("app.db.token_crypto.decrypt_token")
@patch("app.services.linkedin_api.exchange_refresh_for_token")
@patch("app.db.crud_tokens.get_latest_refresh_token")
def test_refresh_happy_path(mock_get_refresh, mock_exchange, mock_decrypt):
    mock_get_refresh.return_value = "enc_dummy"
    mock_decrypt.return_value = "plain_refresh"
    mock_exchange.return_value = {
        "access_token": "new_access",
        "expires_in": 3600,
        "refresh_token": "new_refresh",
        "refresh_token_expires_in": 2592000
    }
    resp = client.post("/auth/linkedin/refresh", json={"user_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["access_token"] == "updated"
    assert data["expires_in"] == 3600
