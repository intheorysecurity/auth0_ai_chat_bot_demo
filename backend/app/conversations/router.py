from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.conversations.service import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
)

router = APIRouter()


class CreateConversationRequest(BaseModel):
    title: str | None = None
    model: str | None = None
    model_id: str | None = None


@router.post("")
async def create_convo(request: CreateConversationRequest, user: dict = Depends(get_current_user)):
    sub = user.get("sub", "")
    cid = await create_conversation(
        sub,
        title=request.title,
        model=request.model,
        model_id=request.model_id,
    )
    return {"conversation_id": cid}


@router.get("")
async def list_convos(user: dict = Depends(get_current_user)):
    sub = user.get("sub", "")
    convos = await list_conversations(sub)
    return {"conversations": convos}


@router.get("/{conversation_id}")
async def get_convo(conversation_id: str, user: dict = Depends(get_current_user)):
    sub = user.get("sub", "")
    convo = await get_conversation(sub, conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"conversation": convo}


@router.delete("/{conversation_id}")
async def delete_convo(conversation_id: str, user: dict = Depends(get_current_user)):
    sub = user.get("sub", "")
    deleted = await delete_conversation(sub, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}
