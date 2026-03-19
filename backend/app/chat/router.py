from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from app.auth.dependencies import get_current_user
from app.chat.models import ChatRequest
from app.chat.service import chat_stream
from app.conversations.service import add_message, create_conversation, set_tool_result, add_tool_call

router = APIRouter()


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    user_id = user.get("sub", "anonymous")
    convo_id = request.conversation_id
    if not convo_id:
        convo_id = await create_conversation(
            user_id,
            model=request.model,
            model_id=request.model_id,
        )

    async def event_generator():
        # Tell the client which conversation this stream belongs to.
        yield f"event: conversation\ndata: {{\"conversation_id\": \"{convo_id}\"}}\n\n"

        # Persist incoming user message (last user message).
        if messages and messages[-1].get("role") == "user":
            await add_message(convo_id, "user", str(messages[-1].get("content", "")))

        assistant_text = ""

        try:
            async for event in chat_stream(
                messages=messages,
                provider_name=request.model,
                model_id=request.model_id,
                mcp_server_urls=request.mcp_server_urls,
                user_id=user_id,
                user_claims=user,
            ):
                # Persist tool events and assistant text deltas
                if event.startswith("event: text_delta"):
                    try:
                        import json as _json
                        data_line = event.split("\n", 1)[1]
                        payload = _json.loads(data_line.replace("data: ", "").strip())
                        assistant_text += str(payload.get("text", ""))
                    except Exception:
                        pass
                if event.startswith("event: tool_call"):
                    # Parse out tool metadata from the SSE line
                    try:
                        import json as _json
                        data_line = event.split("\n", 1)[1]
                        payload = _json.loads(data_line.replace("data: ", "").strip())
                        await add_tool_call(
                            convo_id,
                            payload.get("tool_call_id", ""),
                            payload.get("tool_name", ""),
                            _json.dumps(payload.get("arguments", {})),
                        )
                    except Exception:
                        pass
                elif event.startswith("event: tool_result"):
                    try:
                        import json as _json
                        data_line = event.split("\n", 1)[1]
                        payload = _json.loads(data_line.replace("data: ", "").strip())
                        await set_tool_result(
                            convo_id,
                            payload.get("tool_call_id", ""),
                            payload.get("result", ""),
                        )
                    except Exception:
                        pass
                elif event.startswith("event: done"):
                    if assistant_text.strip():
                        await add_message(convo_id, "assistant", assistant_text)

                yield event
        except Exception as e:
            import json
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
