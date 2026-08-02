from __future__ import annotations

import json
from email.message import Message
from pathlib import Path
from urllib.request import Request

import pytest

from knowledge_engine.google_drive_oauth_refresh import (
    OAuthRefreshError,
    RefreshTokenCredentials,
    load_refresh_token_credentials,
    mint_access_token,
)


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self.headers = Message()

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None


def test_load_refresh_token_credentials_reads_required_fields(tmp_path: Path) -> None:
    credentials_path = tmp_path / "oauth-refresh.json"
    credentials_path.write_text(
        json.dumps(
            {
                "client_id": "client-id.apps.googleusercontent.com",
                "client_secret": "client-secret",
                "refresh_token": "1//refresh-token",
            }
        )
    )

    credentials = load_refresh_token_credentials(credentials_path)

    assert credentials.client_id == "client-id.apps.googleusercontent.com"
    assert credentials.client_secret == "client-secret"
    assert credentials.refresh_token == "1//refresh-token"
    assert credentials.token_uri == "https://oauth2.googleapis.com/token"


def test_load_refresh_token_credentials_rejects_missing_field(tmp_path: Path) -> None:
    credentials_path = tmp_path / "oauth-refresh.json"
    credentials_path.write_text(json.dumps({"client_id": "id", "client_secret": "secret"}))

    with pytest.raises(OAuthRefreshError):
        load_refresh_token_credentials(credentials_path)


def test_load_refresh_token_credentials_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(OAuthRefreshError):
        load_refresh_token_credentials(tmp_path / "does-not-exist.json")


def test_load_refresh_token_credentials_rejects_malformed_json(tmp_path: Path) -> None:
    credentials_path = tmp_path / "oauth-refresh.json"
    credentials_path.write_text("not json")

    with pytest.raises(OAuthRefreshError):
        load_refresh_token_credentials(credentials_path)


def test_mint_access_token_returns_provider_token() -> None:
    credentials = RefreshTokenCredentials(
        client_id="client-id", client_secret="client-secret", refresh_token="1//refresh-token"
    )
    captured: list[Request] = []

    def fake_opener(request: Request) -> FakeResponse:
        captured.append(request)
        return FakeResponse(json.dumps({"access_token": "minted-token"}).encode())

    token = mint_access_token(credentials, opener=fake_opener)

    assert token == "minted-token"
    assert len(captured) == 1
    assert captured[0].full_url == "https://oauth2.googleapis.com/token"
    body = captured[0].data
    assert isinstance(body, bytes)
    from urllib.parse import parse_qs

    parsed = parse_qs(body.decode())
    assert parsed["client_id"][0] == "client-id"
    assert parsed["client_secret"][0] == "client-secret"
    assert parsed["refresh_token"][0] == "1//refresh-token"
    assert parsed["grant_type"][0] == "refresh_token"


def test_mint_access_token_rejects_missing_access_token_in_response() -> None:
    credentials = RefreshTokenCredentials(
        client_id="client-id", client_secret="client-secret", refresh_token="1//refresh-token"
    )

    def fake_opener(request: Request) -> FakeResponse:
        return FakeResponse(json.dumps({"error": "invalid_grant"}).encode())

    with pytest.raises(OAuthRefreshError):
        mint_access_token(credentials, opener=fake_opener)


def test_mint_access_token_wraps_transport_failure() -> None:
    credentials = RefreshTokenCredentials(
        client_id="client-id", client_secret="client-secret", refresh_token="1//refresh-token"
    )

    def failing_opener(request: Request) -> FakeResponse:
        raise OSError("connection refused")

    with pytest.raises(OAuthRefreshError):
        mint_access_token(credentials, opener=failing_opener)
