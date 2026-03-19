from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.mcp_client.manager import McpAuthRequired, mcp_manager
from app.mcp_client.oauth import complete_oauth, start_oauth

router = APIRouter()


class ConnectRequest(BaseModel):
    url: str


class DisconnectRequest(BaseModel):
    url: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


@router.get("/servers")
async def list_servers(user: dict = Depends(get_current_user)):
    return {"servers": mcp_manager.get_connected_servers()}


@router.post("/connect")
async def connect_server(
    request: ConnectRequest,
    user: dict = Depends(get_current_user),
):
    user_id = user.get("sub", "anonymous")
    try:
        tools = await mcp_manager.connect(request.url, user_id)
        return {"status": "connected", "tools": tools}
    except McpAuthRequired as e:
        try:
            auth_url = await start_oauth(
                server_url=request.url,
                user_id=user_id,
                auth_metadata=e.auth_metadata,
            )
            return {"status": "auth_required", "auth_url": auth_url}
        except Exception as oauth_err:
            return {
                "status": "error",
                "message": f"Auth required, but OAuth metadata/discovery failed: {oauth_err}",
            }
    except BaseExceptionGroup as eg:  # py>=3.11
        return {"status": "error", "message": f"Unexpected MCP error: {eg}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/disconnect")
async def disconnect_server(
    request: DisconnectRequest,
    user: dict = Depends(get_current_user),
):
    await mcp_manager.disconnect(request.url)
    return {"status": "disconnected"}


@router.get("/servers/{server_url:path}/tools")
async def list_tools(
    server_url: str,
    user: dict = Depends(get_current_user),
):
    tools = await mcp_manager.list_tools(server_url)
    return {"tools": tools}


@router.post("/oauth/callback")
async def oauth_callback(
    request: OAuthCallbackRequest,
    user: dict = Depends(get_current_user),
):
    try:
        result = await complete_oauth(
            code=request.code,
            state=request.state,
        )
        return result
    except BaseExceptionGroup as eg:  # py>=3.11
        return {"status": "error", "message": f"OAuth callback failed: {eg}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
