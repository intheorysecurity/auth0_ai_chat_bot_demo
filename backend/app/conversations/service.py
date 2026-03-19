from __future__ import annotations

import time
import uuid

from app.db import get_db


async def create_conversation(
    user_sub: str,
    title: str | None = None,
    model: str | None = None,
    model_id: str | None = None,
) -> str:
    conversation_id = f"conv_{uuid.uuid4().hex}"
    async with get_db() as db:
        await db.execute(
            "INSERT INTO conversations (id, user_sub, created_at, title, model, model_id) VALUES (?, ?, ?, ?, ?, ?)",
            (conversation_id, user_sub, time.time(), title, model, model_id),
        )
        await db.commit()
    return conversation_id


async def list_conversations(user_sub: str) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT id, created_at, title, model, model_id FROM conversations WHERE user_sub = ? ORDER BY created_at DESC",
            (user_sub,),
        )
        rows = await cur.fetchall()
        return [
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "title": r["title"],
                "model": r["model"],
                "model_id": r["model_id"],
            }
            for r in rows
        ]


async def get_conversation(user_sub: str, conversation_id: str) -> dict | None:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT id, created_at, title, model, model_id FROM conversations WHERE user_sub = ? AND id = ?",
            (user_sub, conversation_id),
        )
        convo = await cur.fetchone()
        if not convo:
            return None

        mcur = await db.execute(
            "SELECT id, role, content, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        messages = await mcur.fetchall()

        tcur = await db.execute(
            "SELECT id, tool_call_id, tool_name, arguments_json, result_text, created_at "
            "FROM tool_events WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        )
        tools = await tcur.fetchall()

        return {
            "id": convo["id"],
            "created_at": convo["created_at"],
            "title": convo["title"],
            "model": convo["model"],
            "model_id": convo["model_id"],
            "messages": [
                {
                    "id": r["id"],
                    "role": r["role"],
                    "content": r["content"],
                    "created_at": r["created_at"],
                }
                for r in messages
            ],
            "tool_events": [
                {
                    "id": r["id"],
                    "tool_call_id": r["tool_call_id"],
                    "tool_name": r["tool_name"],
                    "arguments_json": r["arguments_json"],
                    "result_text": r["result_text"],
                    "created_at": r["created_at"],
                }
                for r in tools
            ],
        }


async def add_message(conversation_id: str, role: str, content: str) -> str:
    message_id = f"msg_{uuid.uuid4().hex}"
    async with get_db() as db:
        await db.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (message_id, conversation_id, role, content, time.time()),
        )
        await db.commit()
    return message_id


async def add_tool_call(
    conversation_id: str, tool_call_id: str, tool_name: str, arguments_json: str
) -> str:
    event_id = f"tool_{uuid.uuid4().hex}"
    async with get_db() as db:
        await db.execute(
            "INSERT INTO tool_events (id, conversation_id, tool_call_id, tool_name, arguments_json, result_text, created_at) "
            "VALUES (?, ?, ?, ?, ?, NULL, ?)",
            (event_id, conversation_id, tool_call_id, tool_name, arguments_json, time.time()),
        )
        await db.commit()
    return event_id


async def set_tool_result(conversation_id: str, tool_call_id: str, result_text: str) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE tool_events SET result_text = ? WHERE conversation_id = ? AND tool_call_id = ?",
            (result_text, conversation_id, tool_call_id),
        )
        await db.commit()


async def delete_conversation(user_sub: str, conversation_id: str) -> bool:
    """
    Delete a conversation and all associated messages/tool events.
    Returns True if deleted, False if not found for the user.
    """
    async with get_db() as db:
        cur = await db.execute(
            "SELECT id FROM conversations WHERE user_sub = ? AND id = ?",
            (user_sub, conversation_id),
        )
        row = await cur.fetchone()
        if not row:
            return False

        await db.execute("DELETE FROM tool_events WHERE conversation_id = ?", (conversation_id,))
        await db.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        await db.execute(
            "DELETE FROM conversations WHERE id = ? AND user_sub = ?",
            (conversation_id, user_sub),
        )
        await db.commit()
        return True
