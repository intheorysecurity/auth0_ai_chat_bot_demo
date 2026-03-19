import json
import time
from dataclasses import dataclass

import httpx

from app.config import settings


class FgaApiError(Exception):
    """FGA HTTP API returned an error or an unexpected response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: str | None = None,
        url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.body = body or ""
        self.url = url

    def as_dict(self) -> dict:
        d: dict = {
            "error": "fga_api_error",
            "message": self.message,
        }
        if self.status_code is not None:
            d["fga_status_code"] = self.status_code
        if self.body:
            d["fga_body"] = self.body
        if self.url:
            d["fga_url"] = self.url
        return d


def _is_duplicate_tuple_write_error(resp: httpx.Response) -> bool:
    """
    OpenFGA rejects writing the same tuple again (400/409 + message about existing tuple).
    Treat as success so create-order flows stay idempotent.
    """
    if resp.status_code not in (400, 409):
        return False
    raw = (resp.text or "").lower()
    try:
        data = resp.json()
        raw = json.dumps(data).lower()
        code = str(data.get("code", "")).lower()
        msg = str(data.get("message", "")).lower()
    except Exception:
        code = ""
        msg = ""
    combined = f"{raw} {code} {msg}"
    if "already exists" in combined:
        return True
    if "cannot write a tuple which already exists" in combined:
        return True
    if "duplicate" in combined and "tuple" in combined:
        return True
    if resp.status_code == 409 and "conflict" in combined:
        return True
    return False


def _fga_error_from_response(resp: httpx.Response, operation: str) -> FgaApiError:
    text = resp.text or ""
    try:
        parsed = resp.json()
        body_str = json.dumps(parsed) if isinstance(parsed, (dict, list)) else text
    except Exception:
        body_str = text
    url = str(resp.request.url) if resp.request else None
    return FgaApiError(
        f"FGA {operation} failed: HTTP {resp.status_code}",
        status_code=resp.status_code,
        body=body_str,
        url=url,
    )


def _ensure_http_scheme(url: str) -> str:
    """httpx requires http:// or https://; env often has host-only (e.g. api.us1.fga.dev)."""
    u = url.strip()
    if not u:
        return u
    if not u.startswith(("http://", "https://")):
        return f"https://{u}"
    return u


@dataclass
class FgaCheckResult:
    allowed: bool


class FgaClient:
    """
    Minimal OpenFGA/Auth0 FGA HTTP client for:
    - Check
    - Write relationship tuples

    Auth:
    - Prefer static bearer token via `FGA_API_TOKEN`.
    - Otherwise, use client credentials wrapper via:
      `FGA_API_TOKEN_ISSUER`, `FGA_API_AUDIENCE`, `FGA_CLIENT_ID`, `FGA_CLIENT_SECRET`.
    """

    def __init__(self) -> None:
        self._api_url = _ensure_http_scheme(settings.fga_api_url).rstrip("/")
        self._store_id = settings.fga_store_id
        self._model_id = settings.fga_model_id or None

        self._static_token = settings.fga_api_token or None

        raw_issuer = settings.fga_api_token_issuer or None
        self._issuer = _ensure_http_scheme(raw_issuer) if raw_issuer else None
        self._audience = settings.fga_api_audience or None
        self._client_id = settings.fga_client_id or None
        self._client_secret = settings.fga_client_secret or None

        self._cached_access_token: str | None = None
        self._cached_access_token_exp: float = 0.0

    def is_configured(self) -> bool:
        return bool(self._api_url and self._store_id and (self._static_token or self._issuer))

    async def _get_bearer_token(self, client: httpx.AsyncClient) -> str:
        if self._static_token:
            return self._static_token

        now = time.time()
        if self._cached_access_token and (now + 10) < self._cached_access_token_exp:
            return self._cached_access_token

        if not (self._issuer and self._client_id and self._client_secret):
            raise RuntimeError(
                "FGA client credentials not configured. Set FGA_API_TOKEN, "
                "or set FGA_API_TOKEN_ISSUER/FGA_CLIENT_ID/FGA_CLIENT_SECRET (and optionally FGA_API_AUDIENCE)."
            )

        token_url = self._issuer.rstrip("/") + "/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        if self._audience:
            payload["audience"] = self._audience

        resp = await client.post(token_url, data=payload)
        if not resp.is_success:
            raise _fga_error_from_response(resp, "token exchange")
        data = resp.json()
        token = data.get("access_token")
        if not token:
            raise FgaApiError(
                "FGA token exchange succeeded but no access_token in response",
                status_code=resp.status_code,
                body=json.dumps(data) if isinstance(data, dict) else str(data),
                url=str(resp.request.url) if resp.request else None,
            )
        expires_in = float(data.get("expires_in") or 300)
        self._cached_access_token = token
        self._cached_access_token_exp = now + expires_in
        return token

    async def check(self, user: str, relation: str, object: str) -> FgaCheckResult:
        if not self.is_configured():
            raise RuntimeError("FGA is not configured. Set FGA_API_URL and FGA_STORE_ID (and auth settings).")

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                token = await self._get_bearer_token(client)
                url = f"{self._api_url}/stores/{self._store_id}/check"
                body: dict = {
                    "tuple_key": {"user": user, "relation": relation, "object": object},
                }
                if self._model_id:
                    body["authorization_model_id"] = self._model_id

                resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
                if not resp.is_success:
                    raise _fga_error_from_response(resp, "check")
                data = resp.json()
                return FgaCheckResult(allowed=bool(data.get("allowed")))
        except FgaApiError:
            raise
        except httpx.RequestError as e:
            raise FgaApiError(
                f"FGA check request failed: {e}",
                body=str(e),
            ) from e

    async def write_tuples(self, writes: list[dict] | None = None, deletes: list[dict] | None = None) -> None:
        if not self.is_configured():
            raise RuntimeError("FGA is not configured. Set FGA_API_URL and FGA_STORE_ID (and auth settings).")

        writes = writes or []
        deletes = deletes or []

        if not writes and not deletes:
            return

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                token = await self._get_bearer_token(client)
                url = f"{self._api_url}/stores/{self._store_id}/write"
                # Auth0 FGA / OpenFGA reject `deletes: { tuple_keys: [] }` — each block must
                # be omitted when empty, or validation fails with
                # "WriteRequestDeletes.TupleKeys: value must contain at least 1 item(s)".
                body: dict = {}
                if writes:
                    body["writes"] = {"tuple_keys": writes}
                if deletes:
                    body["deletes"] = {"tuple_keys": deletes}
                if self._model_id:
                    body["authorization_model_id"] = self._model_id

                resp = await client.post(url, json=body, headers={"Authorization": f"Bearer {token}"})
                if not resp.is_success:
                    if _is_duplicate_tuple_write_error(resp):
                        return
                    raise _fga_error_from_response(resp, "write")
        except FgaApiError:
            raise
        except httpx.RequestError as e:
            raise FgaApiError(
                f"FGA write request failed: {e}",
                body=str(e),
            ) from e


fga_client = FgaClient()

