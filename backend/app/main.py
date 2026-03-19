from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.dependencies import get_current_user
from app.chat.router import router as chat_router
from app.config import settings
from app.conversations.router import router as conversations_router
from app.ciba.router import router as ciba_router
from app.data.router import router as data_router
from app.llm.router import router as llm_router
from app.mcp_routes.router import router as mcp_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.mcp_client.manager import mcp_manager
    from app.db import init_db

    await init_db()
    yield
    await mcp_manager.shutdown()


app = FastAPI(title="AI Chat Bot", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return {"user": user}


app.include_router(chat_router, prefix="/api/chat")
app.include_router(mcp_router, prefix="/api/mcp")
app.include_router(data_router, prefix="/api/data")
app.include_router(conversations_router, prefix="/api/conversations")
app.include_router(ciba_router, prefix="/api/ciba")
app.include_router(llm_router, prefix="/api/llm")
