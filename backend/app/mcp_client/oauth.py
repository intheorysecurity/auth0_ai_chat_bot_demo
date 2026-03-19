import hashlib
import secrets
from base64 import urlsafe_b64encode
from urllib.parse import urlencode

import certifi
import httpx

from app.config import settings
from app.mcp_client.manager import mcp_manager
from app.mcp_client.models import McpAuthState, OAuthTokens

# In-memory store for pending OAuth states and their auth metadata
_pending_auth: dict[str, McpAuthState] = {}
_pending_auth_metadata: dict[str, dict] = {}


async def start_oauth(
    server_url: str,
    user_id: str,
    auth_metadata: dict,
) -> str:
    """Start the MCP OAuth flow. Returns the authorization URL to redirect the user to."""
    authorization_endpoint = auth_metadata.get("authorization_endpoint", "")
    token_endpoint = auth_metadata.get("token_endpoint", "")
    registration_endpoint = auth_metadata.get("registration_endpoint")

    if not authorization_endpoint:
        raise ValueError("No authorization_endpoint in server metadata")

    # Dynamic client registration if supported
    client_id = ""
    redirect_uri = f"{settings.frontend_url}/mcp/callback"

    if registration_endpoint:
        async with httpx.AsyncClient(verify=certifi.where()) as client:
            reg_resp = await client.post(
                registration_endpoint,
                json={
                    "client_name": "AI Chat Bot Demo",
                    "redirect_uris": [redirect_uri],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                },
            )
            if reg_resp.status_code in (200, 201):
                reg_data = reg_resp.json()
                client_id = reg_data.get("client_id", "")

    if not client_id:
        # Fallback: use a pre-configured client ID or raise
        raise ValueError(
            "Dynamic client registration failed and no pre-configured client_id available."
        )

    # PKCE
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    state = secrets.token_urlsafe(32)

    # Store state and metadata for callback
    _pending_auth_metadata[state] = auth_metadata
    _pending_auth[state] = McpAuthState(
        server_url=server_url,
        user_id=user_id,
        code_verifier=code_verifier,
        client_id=client_id,
        redirect_uri=redirect_uri,
    )

    # Build authorization URL
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    scope = auth_metadata.get("scopes_supported")
    if scope:
        params["scope"] = " ".join(scope[:5])  # Limit scope count

    auth_url = f"{authorization_endpoint}?{urlencode(params)}"
    return auth_url


async def complete_oauth(
    code: str,
    state: str,
) -> dict:
    """Exchange the authorization code for tokens and connect to the MCP server."""
    auth_state = _pending_auth.pop(state, None)
    auth_metadata = _pending_auth_metadata.pop(state, {})
    if not auth_state:
        raise ValueError("Invalid or expired OAuth state")

    token_endpoint = auth_metadata.get("token_endpoint", "")
    if not token_endpoint:
        raise ValueError("No token_endpoint in server metadata")

    # Exchange code for tokens
    async with httpx.AsyncClient(verify=certifi.where()) as client:
        token_resp = await client.post(
            token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": auth_state.redirect_uri,
                "client_id": auth_state.client_id,
                "code_verifier": auth_state.code_verifier,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

    tokens = OAuthTokens(
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_type=token_data.get("token_type", "Bearer"),
        expires_in=token_data.get("expires_in"),
    )

    # Store tokens and retry connection
    mcp_manager.store_tokens(auth_state.user_id, auth_state.server_url, tokens)

    tools = await mcp_manager.connect(auth_state.server_url, auth_state.user_id)
    return {
        "status": "connected",
        "server_url": auth_state.server_url,
        "tools": tools,
    }
