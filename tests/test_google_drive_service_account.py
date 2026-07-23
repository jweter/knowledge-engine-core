from __future__ import annotations

import base64
import json
from email.message import Message
from pathlib import Path
from urllib.request import Request

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from knowledge_engine.google_drive_service_account import (
    ServiceAccountAuthError,
    ServiceAccountKey,
    load_service_account_key,
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


def _generate_private_key_pem() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")


def test_load_service_account_key_reads_required_fields(tmp_path: Path) -> None:
    private_key_pem = _generate_private_key_pem()
    key_path = tmp_path / "service-account.json"
    key_path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "client_email": "backup@example.iam.gserviceaccount.com",
                "private_key": private_key_pem,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )

    key = load_service_account_key(key_path)

    assert key.client_email == "backup@example.iam.gserviceaccount.com"
    assert key.private_key_pem == private_key_pem
    assert key.token_uri == "https://oauth2.googleapis.com/token"


def test_load_service_account_key_rejects_wrong_type(tmp_path: Path) -> None:
    key_path = tmp_path / "service-account.json"
    key_path.write_text(json.dumps({"type": "authorized_user"}))

    with pytest.raises(ServiceAccountAuthError):
        load_service_account_key(key_path)


def test_load_service_account_key_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ServiceAccountAuthError):
        load_service_account_key(tmp_path / "does-not-exist.json")


def test_load_service_account_key_rejects_malformed_json(tmp_path: Path) -> None:
    key_path = tmp_path / "service-account.json"
    key_path.write_text("not json")

    with pytest.raises(ServiceAccountAuthError):
        load_service_account_key(key_path)


def test_mint_access_token_returns_provider_token(tmp_path: Path) -> None:
    private_key_pem = _generate_private_key_pem()
    key = ServiceAccountKey(
        client_email="backup@example.iam.gserviceaccount.com",
        private_key_pem=private_key_pem,
        token_uri="https://oauth2.googleapis.com/token",
    )
    captured: list[Request] = []

    def fake_opener(request: Request) -> FakeResponse:
        captured.append(request)
        return FakeResponse(json.dumps({"access_token": "minted-token"}).encode())

    token = mint_access_token(
        key, scopes=("https://www.googleapis.com/auth/drive.file",), opener=fake_opener
    )

    assert token == "minted-token"
    assert len(captured) == 1
    assert captured[0].full_url == "https://oauth2.googleapis.com/token"
    body = captured[0].data
    assert isinstance(body, bytes)
    assert b"grant_type=urn" in body
    assert b"assertion=" in body


def test_mint_access_token_jwt_assertion_is_well_formed(tmp_path: Path) -> None:
    private_key_pem = _generate_private_key_pem()
    key = ServiceAccountKey(
        client_email="backup@example.iam.gserviceaccount.com",
        private_key_pem=private_key_pem,
    )
    captured: list[Request] = []

    def fake_opener(request: Request) -> FakeResponse:
        captured.append(request)
        return FakeResponse(json.dumps({"access_token": "minted-token"}).encode())

    mint_access_token(
        key, scopes=("https://www.googleapis.com/auth/drive.file",), opener=fake_opener
    )

    body = captured[0].data
    assert isinstance(body, bytes)
    from urllib.parse import parse_qs

    parsed = parse_qs(body.decode())
    assertion = parsed["assertion"][0]
    header_b64, claims_b64, _signature_b64 = assertion.split(".")

    def _decode(segment: str) -> dict[str, object]:
        padding = "=" * (-len(segment) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(segment + padding))
        assert isinstance(decoded, dict)
        return decoded

    header = _decode(header_b64)
    claims = _decode(claims_b64)
    assert header == {"alg": "RS256", "typ": "JWT"}
    assert claims["iss"] == "backup@example.iam.gserviceaccount.com"
    assert claims["scope"] == "https://www.googleapis.com/auth/drive.file"
    assert claims["aud"] == "https://oauth2.googleapis.com/token"
    exp = claims["exp"]
    iat = claims["iat"]
    assert isinstance(exp, int)
    assert isinstance(iat, int)
    assert exp - iat == 3600


def test_mint_access_token_requires_at_least_one_scope() -> None:
    key = ServiceAccountKey(
        client_email="backup@example.iam.gserviceaccount.com",
        private_key_pem=_generate_private_key_pem(),
    )

    with pytest.raises(ServiceAccountAuthError):
        mint_access_token(key, scopes=())


def test_mint_access_token_rejects_missing_access_token_in_response() -> None:
    key = ServiceAccountKey(
        client_email="backup@example.iam.gserviceaccount.com",
        private_key_pem=_generate_private_key_pem(),
    )

    def fake_opener(request: Request) -> FakeResponse:
        return FakeResponse(json.dumps({"error": "invalid_grant"}).encode())

    with pytest.raises(ServiceAccountAuthError):
        mint_access_token(
            key, scopes=("https://www.googleapis.com/auth/drive.file",), opener=fake_opener
        )


def test_mint_access_token_rejects_non_rsa_key() -> None:
    from cryptography.hazmat.primitives.asymmetric import ed25519

    ed_key = ed25519.Ed25519PrivateKey.generate()
    pem = ed_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    key = ServiceAccountKey(
        client_email="backup@example.iam.gserviceaccount.com", private_key_pem=pem
    )

    with pytest.raises(ServiceAccountAuthError):
        mint_access_token(key, scopes=("https://www.googleapis.com/auth/drive.file",))
