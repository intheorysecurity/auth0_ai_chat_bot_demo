from pydantic import BaseModel


class McpServerConfig(BaseModel):
    url: str
    name: str = ""


class OAuthTokens(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int | None = None


class McpAuthState(BaseModel):
    server_url: str
    user_id: str
    code_verifier: str
    client_id: str
    redirect_uri: str
