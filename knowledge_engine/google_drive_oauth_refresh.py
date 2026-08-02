"""Mint short-lived Google Drive OAuth access tokens from a stored refresh token.

A bare Google service account has no Drive storage quota of its own on a
personal (non-Google-Workspace) account -- confirmed live against this
project's actual Drive: read operations succeed (ordinary ACL sharing), but
any write fails with `403 storageQuotaExceeded`. Workspace-only fixes (Shared
Drives, domain-wide delegation) aren't available on a plain Gmail account.
This module authenticates as the human account's own identity instead --
the one that actually owns the Drive quota -- via the standard OAuth
refresh-token grant, so a scheduled script never needs a human to click
through a browser consent screen. The refresh token itself is captured once,
interactively, and stored like any other credential; see
`docs/google_drive_backup_pilot.md`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_TOKEN_URI_DEFAULT = "https://oauth2.googleapis.com/token"


class OAuthRefreshError(RuntimeError):
    """Sanitized OAuth refresh-token failure."""


class HttpResponse(Protocol):
    def read(self) -> bytes: ...

    def __enter__(self) -> HttpResponse: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


OpenUrl = Callable[[Request], HttpResponse]


@dataclass(frozen=True)
class RefreshTokenCredentials:
    """The fields required to exchange a stored refresh token for an access token."""

    client_id: str
    client_secret: str
    refresh_token: str
    token_uri: str = _TOKEN_URI_DEFAULT


def load_refresh_token_credentials(path: Path) -> RefreshTokenCredentials:
    """Read and validate a stored OAuth refresh-token credentials file."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        raise OAuthRefreshError("OAuth refresh-token credentials file is unavailable.") from None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise OAuthRefreshError("OAuth refresh-token credentials file is not valid JSON.") from None
    if not isinstance(payload, dict):
        raise OAuthRefreshError("OAuth refresh-token credentials file has an unexpected shape.")
    client_id = payload.get("client_id")
    client_secret = payload.get("client_secret")
    refresh_token = payload.get("refresh_token")
    if not isinstance(client_id, str) or not client_id:
        raise OAuthRefreshError("OAuth refresh-token credentials file is missing client_id.")
    if not isinstance(client_secret, str) or not client_secret:
        raise OAuthRefreshError("OAuth refresh-token credentials file is missing client_secret.")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise OAuthRefreshError("OAuth refresh-token credentials file is missing refresh_token.")
    token_uri = payload.get("token_uri", _TOKEN_URI_DEFAULT)
    if not isinstance(token_uri, str) or not token_uri:
        token_uri = _TOKEN_URI_DEFAULT
    return RefreshTokenCredentials(
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        token_uri=token_uri,
    )


def mint_access_token(
    credentials: RefreshTokenCredentials,
    *,
    opener: OpenUrl | None = None,
) -> str:
    """Exchange a stored refresh token for a fresh, short-lived access token."""

    body = urlencode(
        {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode()
    request = Request(
        credentials.token_uri,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    call = opener or cast(OpenUrl, urlopen)
    try:
        with call(request) as response:
            raw = response.read()
    except (HTTPError, URLError, OSError):
        raise OAuthRefreshError("Google token refresh request failed.") from None
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OAuthRefreshError("Google token refresh returned an invalid response.") from None
    if not isinstance(payload, dict):
        raise OAuthRefreshError("Google token refresh returned an invalid response.")
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise OAuthRefreshError("Google token refresh did not return an access token.")
    return access_token
