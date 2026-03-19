import json
import uuid
from typing import AsyncIterator

from app.llm.base import Done, StreamChunk, TextDelta, ToolCallRequest
from app.llm.registry import get_provider
from app.data.service import fake_data
from app.fga.client import FgaApiError, fga_client
from app.fga.orders_access import (
    can_read_order,
    ensure_owner_tuple_for_order,
    list_orders_for_principal,
)
from app.ciba.pending_orders import register_pending_ciba_order
from app.ciba.service import ciba_service
from app.mcp_client.manager import mcp_manager

# Helps smaller models (e.g. Ollama) avoid calling unrelated tools (e.g. list_products on “show orders”).
_TOOL_ROUTING_HINT = (
    "When you call tools, use only what the user asked for. "
    "Questions about orders, purchases, order history, or cancellations → use list_orders and/or get_order. "
    "Do not call list_products or get_product for those unless the user also asked about the product catalog. "
    "Questions about products, catalog, SKUs, or what is for sale → use list_products and/or get_product. "
    "If the user only asks to list or show their orders, call list_orders once. "
    "Do not call whoami, check_permission, or get_product for a simple order list unless the user explicitly asks for identity, permissions, or product catalog details."
)

_RESPONSE_STYLE_HINT = (
    "Reply only with the final answer for the user. "
    "Do not include hidden reasoning, planning, meta-commentary, or phrases like "
    "'The user wants', 'I need to', 'Let me call', or analysis meant for yourself. "
    "After tools return, summarize briefly in clean markdown; avoid broken tables or filler punctuation."
)


def _inject_tool_routing_hint(messages: list[dict]) -> list[dict]:
    """Prepend tool-routing + response-style guidance; merge into first system message."""
    combined = f"{_TOOL_ROUTING_HINT}\n\n{_RESPONSE_STYLE_HINT}"
    msgs = list(messages)
    if not msgs:
        return [{"role": "system", "content": combined}]
    if msgs[0].get("role") == "system":
        existing = str(msgs[0].get("content") or "").strip()
        merged = f"{combined}\n\n{existing}" if existing else combined
        msgs[0] = {**msgs[0], "content": merged}
        return msgs
    return [{"role": "system", "content": combined}] + msgs


async def chat_stream(
    messages: list[dict],
    provider_name: str,
    model_id: str | None,
    mcp_server_urls: list[str],
    user_id: str,
    user_claims: dict,
) -> AsyncIterator[str]:
    """Orchestrate LLM streaming with MCP tool-use loop. Yields SSE-formatted strings."""
    provider = get_provider(provider_name)

    # Deterministic builtin tool: whoami
    # If the user asks for identity, don't rely on the model—return verified claims.
    if messages:
        last = messages[-1]
        if last.get("role") == "user":
            normalized = (
                str(last.get("content", "")).strip().lower().rstrip("?.!")
            )
            if normalized in {"whoami", "who am i"}:
                tool_call_id = f"whoami_{uuid.uuid4().hex}"
                yield _sse(
                    "tool_call",
                    {"tool_call_id": tool_call_id, "tool_name": "whoami", "arguments": {}},
                )
                result = _whoami_result(user_claims, user_id)
                yield _sse(
                    "tool_result",
                    {"tool_call_id": tool_call_id, "result": result},
                )
                yield _sse("done", {"usage": None})
                return

    # Gather tools from connected MCP servers
    tools: list[dict] = []
    tools.append(
        {
            "name": "whoami",
            "description": "Return the authenticated user's identity (verified by the server).",
            "input_schema": {"type": "object", "additionalProperties": False},
        }
    )
    tools.append(
        {
            "name": "check_permission",
            "description": "Check whether the current user has a relation on an object (Auth0 FGA/OpenFGA).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "relation": {"type": "string"},
                    "object": {"type": "string"},
                },
                "required": ["relation", "object"],
                "additionalProperties": False,
            },
        }
    )
    tools.append(
        {
            "name": "list_orders",
            "description": (
                "List the user's orders from the simulated store. Each order includes product_id, product_name, "
                "totals, status, buyer_email, company — you usually do NOT need get_product or whoami afterward. "
                "When FGA is configured, only orders the user may read are returned; when FGA is off, all demo orders are visible."
            ),
            "input_schema": {"type": "object", "additionalProperties": False},
        }
    )
    tools.append(
        {
            "name": "get_order",
            "description": (
                "Fetch a single order by id. Use for one specific order; not for listing the catalog. "
                "When FGA is configured, requires can_read on that order."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
        }
    )
    tools.append(
        {
            "name": "list_products",
            "description": (
                "List products in the catalog (items for sale, SKUs). "
                "Do not use for orders or purchase history — use list_orders instead."
            ),
            "input_schema": {"type": "object", "additionalProperties": False},
        }
    )
    tools.append(
        {
            "name": "get_product",
            "description": (
                "Get one catalog product by id. For order records by id, use get_order instead."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
                "additionalProperties": False,
            },
        }
    )
    tools.append(
        {
            "name": "create_order",
            "description": (
                "Create an order for the current user (simulated data). "
                "If the backend returns status approval_required (high-value purchase with CIBA configured), "
                "**no order exists yet** — the user must approve on their device; the order is created only after "
                "approval when the client polls CIBA. Do not tell the user the purchase is complete until the tool "
                "result includes a finalized order with status created."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "company": {
                        "type": "string",
                        "description": "Optional company name for the buyer (defaults to Personal).",
                    },
                },
                "required": ["product_id", "quantity"],
                "additionalProperties": False,
            },
        }
    )
    tools.append(
        {
            "name": "cancel_order",
            "description": "Cancel an order by ID (requires can_write permission via FGA when configured).",
            "input_schema": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
                "additionalProperties": False,
            },
        }
    )
    for url in mcp_server_urls:
        server_tools = await mcp_manager.list_tools(url)
        tools.extend(server_tools)

    # Keep a mutable copy of messages for the tool-use loop
    working_messages = _inject_tool_routing_hint(list(messages))
    max_tool_rounds = 10

    for _ in range(max_tool_rounds):
        tool_calls_this_round: list[ToolCallRequest] = []

        async for chunk in provider.stream_chat(
            messages=working_messages,
            model=model_id,
            tools=tools or None,
        ):
            if isinstance(chunk, TextDelta):
                yield _sse("text_delta", {"text": chunk.text})
            elif isinstance(chunk, ToolCallRequest):
                tool_calls_this_round.append(chunk)
                yield _sse("tool_call", {
                    "tool_call_id": chunk.tool_call_id,
                    "tool_name": chunk.tool_name,
                    "arguments": chunk.arguments,
                })
            elif isinstance(chunk, Done):
                if not tool_calls_this_round:
                    yield _sse("done", {"usage": chunk.usage})

        if not tool_calls_this_round:
            break

        # Execute tool calls and feed results back
        # Add assistant message with tool calls to history
        assistant_content = []
        for tc in tool_calls_this_round:
            assistant_content.append({
                "type": "tool_use",
                "id": tc.tool_call_id,
                "name": tc.tool_name,
                "input": tc.arguments,
            })

        # For Anthropic-style messages
        if provider_name == "claude":
            working_messages.append({"role": "assistant", "content": assistant_content})
            for tc in tool_calls_this_round:
                result = await _execute_tool(tc, mcp_server_urls, user_claims, user_id)
                yield _sse("tool_result", {
                    "tool_call_id": tc.tool_call_id,
                    "result": result,
                })
                working_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tc.tool_call_id,
                            "content": result,
                        }
                    ],
                })
        else:
            if provider_name == "ollama":
                # Ollama expects tool_calls.function.arguments as an object (not a JSON string),
                # and tool results should include tool_name (no tool_call_id field).
                working_messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": tc.tool_name,
                                    "arguments": tc.arguments,
                                }
                            }
                            for tc in tool_calls_this_round
                        ],
                    }
                )
                for tc in tool_calls_this_round:
                    result = await _execute_tool(tc, mcp_server_urls, user_claims, user_id)
                    yield _sse(
                        "tool_result",
                        {"tool_call_id": tc.tool_call_id, "result": result},
                    )
                    working_messages.append(
                        {
                            "role": "tool",
                            "content": result,
                            "tool_name": tc.tool_name,
                        }
                    )
            else:
                # OpenAI style: assistant message with tool_calls, then tool messages
                working_messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.tool_call_id,
                                "type": "function",
                                "function": {
                                    "name": tc.tool_name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in tool_calls_this_round
                        ],
                    }
                )
                for tc in tool_calls_this_round:
                    result = await _execute_tool(tc, mcp_server_urls, user_claims, user_id)
                    yield _sse(
                        "tool_result",
                        {"tool_call_id": tc.tool_call_id, "result": result},
                    )
                    working_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.tool_call_id,
                            "content": result,
                        }
                    )


async def _execute_tool(
    tc: ToolCallRequest,
    mcp_server_urls: list[str],
    user_claims: dict,
    user_id: str,
) -> str:
    """Execute a tool call against the appropriate MCP server."""
    if tc.tool_name == "whoami":
        return _whoami_result(user_claims, user_id)

    if tc.tool_name == "check_permission":
        relation = str(tc.arguments.get("relation", ""))
        obj = str(tc.arguments.get("object", ""))
        if not relation or not obj:
            return json.dumps({"error": "relation and object are required"})
        if not fga_client.is_configured():
            return json.dumps({"configured": False, "allowed": False, "error": "FGA not configured"})
        try:
            res = await fga_client.check(user=f"user:{user_id}", relation=relation, object=obj)
            return json.dumps(
                {
                    "configured": True,
                    "allowed": res.allowed,
                    "fga_check": {
                        "user": f"user:{user_id}",
                        "relation": relation,
                        "object": obj,
                    },
                }
            )
        except FgaApiError as e:
            return json.dumps({"configured": True, **e.as_dict(), "context": "check_permission"})

    if tc.tool_name == "list_products":
        return json.dumps({"products": fake_data.list_products()})

    if tc.tool_name == "get_product":
        pid = str(tc.arguments.get("product_id", ""))
        p = fake_data.get_product(pid)
        return json.dumps({"product": p})

    if tc.tool_name == "list_orders":
        try:
            raw_orders = await list_orders_for_principal(user_id)
            enriched: list[dict] = []
            for o in raw_orders:
                row = dict(o)
                pid = str(o.get("product_id", "") or "")
                p = fake_data.get_product(pid) if pid else None
                row["product_name"] = p.get("name") if p else None
                enriched.append(row)
            return json.dumps({"orders": enriched})
        except FgaApiError as e:
            return json.dumps({"orders": [], **e.as_dict(), "context": "list_orders"})

    if tc.tool_name == "get_order":
        oid = str(tc.arguments.get("order_id", ""))
        o = fake_data.get_order(oid)
        if not o:
            return json.dumps({"error": "not_found", "detail": "Unknown order_id"})
        if fga_client.is_configured():
            try:
                allowed = await can_read_order(user_id, oid)
            except FgaApiError as e:
                return json.dumps({**e.as_dict(), "context": "get_order_can_read"})
            if not allowed:
                return json.dumps(
                    {
                        "error": "not_authorized",
                        "detail": "can_read denied",
                        "fga_check": {
                            "allowed": False,
                            "user": f"user:{user_id}",
                            "relation": "can_read",
                            "object": f"order:{oid}",
                        },
                    }
                )
        return json.dumps({"order": o})

    if tc.tool_name == "create_order":
        pid = str(tc.arguments.get("product_id", ""))
        qty = int(tc.arguments.get("quantity", 1) or 1)
        company_arg = tc.arguments.get("company")
        company = str(company_arg).strip() if company_arg is not None else None
        buyer_email = user_claims.get("email")
        if not isinstance(buyer_email, str) or not buyer_email.strip():
            buyer_email = None
        # High-risk writes require CIBA step-up (if configured).
        # For demo: require step-up when total exceeds $25.00.
        p = fake_data.get_product(pid)
        if not p:
            return json.dumps({"error": "invalid_request", "detail": "Unknown product_id"})
        total = int(p["price_cents"]) * qty
        if ciba_service.is_configured() and total >= 2500:
            start = await ciba_service.start(
                login_hint=user_id,
                scope="openid",
                # Auth0 binding_message: no $, parens, etc. — sanitized again in ciba_service.start
                binding_message=(
                    f"Approve purchase {qty}x {p['name']}, total USD {total/100:.2f}"
                ),
            )
            # Defer persistence: no order row (and no FGA owner tuple) until CIBA poll returns approved.
            register_pending_ciba_order(
                auth_req_id=start.auth_req_id,
                buyer_sub=user_id,
                product_id=pid,
                quantity=qty,
                company=company,
                buyer_email=buyer_email,
            )
            try:
                raw_iv = start.interval
                poll_iv = int(raw_iv) if raw_iv is not None else 3
            except (TypeError, ValueError):
                poll_iv = 3
            poll_iv = max(2, min(poll_iv, 15))
            payload: dict = {
                "status": "approval_required",
                "auth_req_id": start.auth_req_id,
                "product_id": pid,
                "quantity": qty,
                "total_cents": total,
                "product_name": p["name"],
                "poll_interval_sec": poll_iv,
                "approval_timeout_sec": 60,
                "message": (
                    "CIBA started. **No order has been created yet.** "
                    "The app polls approval automatically; the user should approve on their device. "
                    "If no approval within 60 seconds, the checkout is cancelled. "
                    "After approval, the order appears in the next poll result."
                ),
            }
            return json.dumps(payload)

        order = fake_data.create_order(
            product_id=pid,
            buyer_sub=user_id,
            quantity=qty,
            company=company,
            buyer_email=buyer_email,
        )
        try:
            await ensure_owner_tuple_for_order(user_id, str(order["id"]))
        except FgaApiError as e:
            return json.dumps(
                {
                    "order": order,
                    "fga_owner": "failed",
                    "fga_owner_tuple_error": e.as_dict(),
                }
            )
        return json.dumps({"order": order, "fga_owner": "ok"})

    if tc.tool_name == "cancel_order":
        oid = str(tc.arguments.get("order_id", ""))
        if fga_client.is_configured():
            try:
                res = await fga_client.check(
                    user=f"user:{user_id}", relation="can_write", object=f"order:{oid}"
                )
            except FgaApiError as e:
                return json.dumps({**e.as_dict(), "context": "cancel_order_check"})
            if not res.allowed:
                return json.dumps(
                    {
                        "error": "not_authorized",
                        "detail": "can_write denied",
                        "fga_check": {
                            "allowed": False,
                            "user": f"user:{user_id}",
                            "relation": "can_write",
                            "object": f"order:{oid}",
                        },
                    }
                )
        try:
            order = fake_data.cancel_order(oid)
            return json.dumps({"order": order})
        except ValueError as e:
            return json.dumps({"error": "not_found", "detail": str(e)})

    for url in mcp_server_urls:
        server_tools = await mcp_manager.list_tools(url)
        tool_names = [t["name"] for t in server_tools]
        if tc.tool_name in tool_names:
            result = await mcp_manager.call_tool(url, tc.tool_name, tc.arguments)
            return result
    return f"Error: Tool '{tc.tool_name}' not found on any connected MCP server."


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _whoami_result(user_claims: dict, user_id: str) -> str:
    safe = {
        "sub": user_claims.get("sub") or user_id,
        "name": user_claims.get("name"),
        "email": user_claims.get("email"),
        "iss": user_claims.get("iss"),
        "aud": user_claims.get("aud"),
    }
    # Drop nulls for cleaner output
    safe = {k: v for k, v in safe.items() if v is not None}
    return json.dumps(safe)
