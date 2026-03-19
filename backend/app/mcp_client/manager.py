import json
import logging
import re

import certifi
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.mcp_client.models import OAuthTokens

logger = logging.getLogger(__name__)


class McpAuthRequired(Exception):
    """Raised when an MCP server requires OAuth authentication."""

    def __init__(self, server_url: str, auth_metadata: dict):
        self.server_url = server_url
        self.auth_metadata = auth_metadata
        super().__init__(f"MCP server {server_url} requires authentication")


class MCPManager:
    def __init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}
        # Store streamable-http transport context managers to keep them alive.
        # If they are not referenced, they can be garbage-collected and their async cleanup
        # may run in a different task, which AnyIO does not allow.
        self._contexts: dict[str, object] = {}
        self._tools_cache: dict[str, list[dict]] = {}
        self._token_store: dict[tuple[str, str], OAuthTokens] = {}

    def store_tokens(self, user_id: str, server_url: str, tokens: OAuthTokens) -> None:
        self._token_store[(user_id, server_url)] = tokens

    def get_tokens(self, user_id: str, server_url: str) -> OAuthTokens | None:
        return self._token_store.get((user_id, server_url))

    async def connect(self, server_url: str, user_id: str = "") -> list[dict]:
        """Connect to an MCP server. Returns list of tool definitions.

        Raises McpAuthRequired if the server requires OAuth.
        """
        if server_url in self._sessions:
            return self._tools_cache.get(server_url, [])

        headers = {}
        tokens = self.get_tokens(user_id, server_url) if user_id else None
        if tokens:
            headers["Authorization"] = f"{tokens.token_type} {tokens.access_token}"

        try:
            # Try connecting to the MCP server
            async with httpx.AsyncClient(verify=certifi.where()) as client:
                # First, probe the server to check if auth is required
                probe_resp = await client.get(server_url, headers=headers)
                if probe_resp.status_code == 401:
                    resource_meta_url = self._extract_resource_metadata_url(
                        probe_resp.headers.get("www-authenticate", "")
                    )
                    auth_metadata = await self._fetch_auth_metadata(
                        server_url, resource_metadata_url=resource_meta_url
                    )
                    raise McpAuthRequired(server_url, auth_metadata)

            # Connect using MCP SDK (streamable HTTP transport).
            # IMPORTANT: keep the context manager alive for the lifetime of the session.
            transport_cm = streamablehttp_client(server_url, headers=headers)
            try:
                read_stream, write_stream, _ = await transport_cm.__aenter__()
            except Exception:
                # Ensure we don't leave a half-open transport around.
                try:
                    await transport_cm.__aexit__(None, None, None)
                except Exception:
                    pass
                raise

            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            self._sessions[server_url] = session
            self._contexts[server_url] = transport_cm

            # Cache tools
            tools_result = await session.list_tools()
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else {"type": "object"},
                }
                for tool in tools_result.tools
            ]
            self._tools_cache[server_url] = tools

            return tools

        except McpAuthRequired:
            raise
        except Exception as e:
            logger.error(f"Failed to connect to MCP server {server_url}: {e}")
            raise

    def _extract_resource_metadata_url(self, www_authenticate: str) -> str | None:
        """
        Parse `WWW-Authenticate` for RFC 9728 `resource_metadata="<url>"`.

        Example header:
        Bearer ..., resource_metadata="https://host/.well-known/oauth-protected-resource/mcp"
        """
        if not www_authenticate:
            return None
        m = re.search(r'resource_metadata="([^"]+)"', www_authenticate)
        return m.group(1) if m else None

    async def _fetch_auth_metadata(
        self, server_url: str, resource_metadata_url: str | None = None
    ) -> dict:
        """Fetch OAuth metadata from the MCP server's protected resource metadata endpoint."""
        from urllib.parse import urlparse
        parsed = urlparse(server_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        async with httpx.AsyncClient(verify=certifi.where()) as client:
            # Try RFC 9728 protected resource metadata endpoint(s)
            try:
                urls_to_try: list[str] = []
                if resource_metadata_url:
                    urls_to_try.append(resource_metadata_url)

                # Common default
                urls_to_try.append(f"{base}/.well-known/oauth-protected-resource")

                # Some servers scope metadata by resource path, e.g.
                # `/.well-known/oauth-protected-resource/mcp` for `/mcp`.
                path = (parsed.path or "").rstrip("/")
                if path:
                    urls_to_try.append(
                        f"{base}/.well-known/oauth-protected-resource{path}"
                    )

                resource_meta = None
                for url in urls_to_try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        resource_meta = resp.json()
                        break

                if resource_meta:
                    # Fetch authorization server metadata
                    auth_server = resource_meta.get("authorization_servers", [None])[0]
                    if auth_server:
                        auth_server = str(auth_server).rstrip("/")
                        as_resp = await client.get(
                            f"{auth_server}/.well-known/oauth-authorization-server"
                        )
                        if as_resp.status_code == 200:
                            return as_resp.json()
            except Exception:
                pass

            # Fallback: try well-known/openid-configuration
            try:
                resp = await client.get(f"{base}/.well-known/openid-configuration")
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass

        return {}

    async def disconnect(self, server_url: str) -> None:
        session = self._sessions.pop(server_url, None)
        if session:
            try:
                await session.__aexit__(None, None, None)
            except Exception:
                pass
        transport_cm = self._contexts.pop(server_url, None)
        if transport_cm:
            try:
                await transport_cm.__aexit__(None, None, None)  # type: ignore[attr-defined]
            except Exception:
                # Some transports may raise AnyIO cancel-scope errors if closed from a
                # different task than opened; don't let that crash the API.
                pass
        self._tools_cache.pop(server_url, None)

    async def list_tools(self, server_url: str) -> list[dict]:
        return self._tools_cache.get(server_url, [])

    async def call_tool(self, server_url: str, tool_name: str, arguments: dict) -> str:
        session = self._sessions.get(server_url)
        if not session:
            return f"Error: Not connected to MCP server {server_url}"

        try:
            result = await session.call_tool(tool_name, arguments)
            # Extract text content from the result
            texts = []
            for content in result.content:
                if hasattr(content, "text"):
                    texts.append(content.text)
                else:
                    texts.append(str(content))
            return "\n".join(texts) if texts else "Tool returned no content."
        except Exception as e:
            return f"Error calling tool {tool_name}: {e}"

    def get_connected_servers(self) -> list[dict]:
        return [
            {
                "url": url,
                "tools_count": len(self._tools_cache.get(url, [])),
                "tools": self._tools_cache.get(url, []),
                "connected": True,
            }
            for url in self._sessions
        ]

    async def shutdown(self) -> None:
        for url in list(self._sessions.keys()):
            await self.disconnect(url)


mcp_manager = MCPManager()
