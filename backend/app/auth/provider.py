from abc import ABC, abstractmethod

import ssl
import time

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
import json as _json

from app.config import settings


def _default_ssl_context() -> ssl.SSLContext:
    """
    Use certifi's CA bundle when available to avoid local trust-store issues
    (common in some Python installs/venvs on macOS).
    """
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class JWKSCache:
    def __init__(self, jwks_url: str, ttl_seconds: int = 3600) -> None:
        self._jwks_url = jwks_url
        self._ttl_seconds = ttl_seconds
        self._cached_at: float = 0.0
        self._jwks: dict | None = None

    async def get(self) -> dict:
        now = time.time()
        if self._jwks and (now - self._cached_at) < self._ttl_seconds:
            return self._jwks

        # Use httpx and ignore proxy env vars (fixes urllib tunnel 403s).
        ssl_context = _default_ssl_context()
        async with httpx.AsyncClient(timeout=20.0, verify=ssl_context, trust_env=False) as client:
            resp = await client.get(self._jwks_url)
            resp.raise_for_status()
            jwks = resp.json()

        self._jwks = jwks
        self._cached_at = now
        return jwks

    async def get_key_for_kid(self, kid: str) -> object:
        jwks = await self.get()
        keys = jwks.get("keys", [])
        for k in keys:
            if k.get("kid") == kid:
                return RSAAlgorithm.from_jwk(_json.dumps(k))
        raise ValueError(f"JWKS key not found for kid={kid}")


class AuthProvider(ABC):
    @abstractmethod
    async def validate_token(self, token: str) -> dict:
        """Validate a JWT and return the decoded claims."""
        ...


class Auth0Provider(AuthProvider):
    def __init__(self) -> None:
        self._domain = settings.auth0_domain
        self._audience = settings.auth0_audience
        self._issuer = f"https://{self._domain}/"
        self._jwks_url = f"https://{self._domain}/.well-known/jwks.json"
        self._jwks_cache = JWKSCache(self._jwks_url)

    async def validate_token(self, token: str) -> dict:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise ValueError("JWT header missing 'kid'")
        signing_key = await self._jwks_cache.get_key_for_kid(kid)
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=self._audience,
            issuer=self._issuer,
        )
        return payload


class OktaProvider(AuthProvider):
    """Placeholder for Okta integration. Same pattern as Auth0 with different endpoints."""

    def __init__(self) -> None:
        self._issuer = settings.okta_issuer
        self._audience = settings.okta_audience
        self._jwks_url = f"{self._issuer}/v1/keys"
        self._jwks_cache = JWKSCache(self._jwks_url)

    async def validate_token(self, token: str) -> dict:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise ValueError("JWT header missing 'kid'")
        signing_key = await self._jwks_cache.get_key_for_kid(kid)
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=self._audience,
            issuer=self._issuer,
        )
        return payload


def get_auth_provider() -> AuthProvider:
    if settings.auth_provider == "okta":
        return OktaProvider()
    return Auth0Provider()


auth_provider = get_auth_provider()
