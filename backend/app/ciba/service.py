from __future__ import annotations

import json
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx

from app.config import settings


def _auth0_login_hint(*, sub: str, issuer_url: str) -> str:
    """
    Auth0 /bc-authorize expects `login_hint` to be JSON (not a bare subject).

    See: https://auth0.com/docs/.../user-authorization-with-ciba
    Example: {"format":"iss_sub","iss":"https://YOUR_TENANT.auth0.com/","sub":"USER_ID"}
    """
    base = issuer_url.strip().rstrip("/")
    iss = f"{base}/"
    return json.dumps(
        {"format": "iss_sub", "iss": iss, "sub": sub},
        separators=(",", ":"),
    )


def sanitize_binding_message(text: str, *, max_len: int = 128) -> str:
    """
    Auth0 rejects binding_message characters outside:
    alphanumerics, whitespace, and + - _ . , : #
    (e.g. `$`, parentheses, `@` are not allowed.)
    """
    allowed = frozenset(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+-_.,:#"
    )
    out: list[str] = []
    for ch in text:
        if ch in allowed:
            out.append(ch)
        elif ch.isspace():
            out.append(" ")
        else:
            out.append(" ")
    s = " ".join("".join(out).split())
    if not s:
        s = "Approve this action"
    return s[:max_len].rstrip()


@dataclass
class CibaStartResult:
    auth_req_id: str
    expires_in: int | None = None
    interval: int | None = None


class CibaService:
    def __init__(self) -> None:
        self._issuer = settings.auth0_issuer_url.rstrip("/") + "/" if settings.auth0_issuer_url else ""
        self._client_id = settings.auth0_ciba_client_id
        self._client_secret = settings.auth0_ciba_client_secret
        self._audience = settings.auth0_ciba_audience or None

        self._authz_ep = (
            settings.auth0_ciba_authorization_endpoint
            or (urljoin(self._issuer, "bc-authorize") if self._issuer else "")
        )
        self._token_ep = (
            settings.auth0_ciba_token_endpoint
            or (urljoin(self._issuer, "oauth/token") if self._issuer else "")
        )

    def is_configured(self) -> bool:
        return bool(self._issuer and self._client_id and self._client_secret and self._authz_ep and self._token_ep)

    async def start(
        self,
        *,
        login_hint: str,
        scope: str = "openid",
        binding_message: str | None = None,
    ) -> CibaStartResult:
        if not self.is_configured():
            raise RuntimeError("CIBA is not configured. Set AUTH0_ISSUER_URL and AUTH0_CIBA_CLIENT_ID/SECRET.")

        issuer = (settings.auth0_issuer_url or "").strip()
        if not issuer:
            raise RuntimeError("AUTH0_ISSUER_URL is required to build CIBA login_hint (iss_sub JSON).")

        data: dict[str, str] = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "scope": scope,
            "login_hint": _auth0_login_hint(sub=login_hint, issuer_url=issuer),
        }
        if self._audience:
            data["audience"] = self._audience
        if binding_message:
            data["binding_message"] = sanitize_binding_message(binding_message)

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(self._authz_ep, data=data)
            resp.raise_for_status()
            payload = resp.json()
            return CibaStartResult(
                auth_req_id=payload["auth_req_id"],
                expires_in=payload.get("expires_in"),
                interval=payload.get("interval"),
            )

    async def poll(self, *, auth_req_id: str) -> dict:
        if not self.is_configured():
            raise RuntimeError("CIBA is not configured.")

        data = {
            "grant_type": "urn:openid:params:grant-type:ciba",
            "auth_req_id": auth_req_id,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(self._token_ep, data=data)
            # RFC: while pending, token endpoint often returns 400 with {error:"authorization_pending"}
            if resp.status_code == 200:
                return {"status": "approved", "token": resp.json()}
            try:
                payload = resp.json()
            except Exception:
                payload = {"error": resp.text}

            err = str(payload.get("error", ""))
            if err in {"authorization_pending", "slow_down"}:
                return {"status": "pending", **payload}
            if err in {"access_denied", "expired_token"}:
                return {"status": "denied", **payload}
            return {"status": "error", "http_status": resp.status_code, **payload}


ciba_service = CibaService()

