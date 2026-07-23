"""Mint short-lived Google Drive OAuth access tokens from a service-account key.

Implements the standard Google JWT-bearer token exchange (RFC 7523) directly
with `cryptography` and stdlib `urllib`, matching `google_drive_http.py`'s
existing preference for a minimal, dependency-light HTTP transport over the
full `google-api-python-client`/`google-auth` SDKs.

The service-account key file itself is never read by any code path other
than this module, and its contents are never logged, printed, or persisted
anywhere other than the caller-supplied path on local disk.
"""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

_TOKEN_URI_DEFAULT = "https://oauth2.googleapis.com/token"
_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"
_TOKEN_LIFETIME_SECONDS = 3600


class ServiceAccountAuthError(RuntimeError):
    """Sanitized service-account authorization failure."""


class HttpResponse(Protocol):
    def read(self) -> bytes: ...

    def __enter__(self) -> HttpResponse: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


OpenUrl = Callable[[Request], HttpResponse]


@dataclass(frozen=True)
class ServiceAccountKey:
    """The fields of a Google service-account JSON key required for signing."""

    client_email: str
    private_key_pem: str
    token_uri: str = _TOKEN_URI_DEFAULT


def load_service_account_key(path: Path) -> ServiceAccountKey:
    """Read and validate a service-account JSON key file."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        raise ServiceAccountAuthError("Service-account key file is unavailable.") from None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise ServiceAccountAuthError("Service-account key file is not valid JSON.") from None
    if not isinstance(payload, dict) or payload.get("type") != "service_account":
        raise ServiceAccountAuthError("Service-account key file has an unexpected shape.")
    client_email = payload.get("client_email")
    private_key_pem = payload.get("private_key")
    if not isinstance(client_email, str) or not client_email:
        raise ServiceAccountAuthError("Service-account key file is missing client_email.")
    if not isinstance(private_key_pem, str) or not private_key_pem:
        raise ServiceAccountAuthError("Service-account key file is missing private_key.")
    token_uri = payload.get("token_uri", _TOKEN_URI_DEFAULT)
    if not isinstance(token_uri, str) or not token_uri:
        token_uri = _TOKEN_URI_DEFAULT
    return ServiceAccountKey(
        client_email=client_email, private_key_pem=private_key_pem, token_uri=token_uri
    )


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _build_signed_jwt(key: ServiceAccountKey, scopes: tuple[str, ...], now: int) -> str:
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": key.client_email,
        "scope": " ".join(scopes),
        "aud": key.token_uri,
        "iat": now,
        "exp": now + _TOKEN_LIFETIME_SECONDS,
    }
    signing_input = (
        f"{_base64url(json.dumps(header, separators=(',', ':')).encode())}"
        f".{_base64url(json.dumps(claims, separators=(',', ':')).encode())}"
    )
    try:
        private_key = serialization.load_pem_private_key(
            key.private_key_pem.encode("ascii"), password=None
        )
    except ValueError:
        raise ServiceAccountAuthError("Service-account private key could not be parsed.") from None
    if not isinstance(private_key, RSAPrivateKey):
        raise ServiceAccountAuthError("Service-account private key must be RSA.")
    signature = private_key.sign(signing_input.encode("ascii"), padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input}.{_base64url(signature)}"


def mint_access_token(
    key: ServiceAccountKey,
    *,
    scopes: tuple[str, ...],
    opener: OpenUrl | None = None,
) -> str:
    """Exchange one signed JWT assertion for a short-lived Drive access token."""

    if not scopes:
        raise ServiceAccountAuthError("At least one OAuth scope is required.")
    assertion = _build_signed_jwt(key, scopes, int(time.time()))
    body = urlencode({"grant_type": _GRANT_TYPE, "assertion": assertion}).encode()
    request = Request(
        key.token_uri,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    call = opener or cast(OpenUrl, urlopen)
    try:
        with call(request) as response:
            raw = response.read()
    except (HTTPError, URLError, OSError):
        raise ServiceAccountAuthError("Google token exchange request failed.") from None
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ServiceAccountAuthError(
            "Google token exchange returned an invalid response."
        ) from None
    if not isinstance(payload, dict):
        raise ServiceAccountAuthError("Google token exchange returned an invalid response.")
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ServiceAccountAuthError("Google token exchange did not return an access token.")
    return access_token
