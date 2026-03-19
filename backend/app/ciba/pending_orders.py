"""
In-memory pending checkouts for CIBA: order is NOT persisted until the user approves
and POST /api/ciba/poll returns status approved.

Lost on process restart (demo limitation).
"""

from __future__ import annotations

from typing import Any

# auth_req_id -> checkout payload (must match buyer_sub on finalize)
_pending: dict[str, dict[str, Any]] = {}


def register_pending_ciba_order(
    *,
    auth_req_id: str,
    buyer_sub: str,
    product_id: str,
    quantity: int,
    company: str | None,
    buyer_email: str | None,
) -> None:
    _pending[auth_req_id] = {
        "buyer_sub": buyer_sub,
        "product_id": product_id,
        "quantity": quantity,
        "company": company,
        "buyer_email": buyer_email,
    }


def take_pending_ciba_order(auth_req_id: str, buyer_sub: str) -> dict[str, Any] | None:
    """Remove and return pending checkout if auth_req_id and sub match."""
    row = _pending.get(auth_req_id)
    if not row or row.get("buyer_sub") != buyer_sub:
        return None
    del _pending[auth_req_id]
    return row


def discard_pending_ciba_order(auth_req_id: str, buyer_sub: str) -> None:
    """Drop intent when CIBA is denied/expired so the user can start a new checkout."""
    row = _pending.get(auth_req_id)
    if row and row.get("buyer_sub") == buyer_sub:
        del _pending[auth_req_id]
