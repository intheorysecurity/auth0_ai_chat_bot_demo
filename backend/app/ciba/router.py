from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.ciba.pending_orders import discard_pending_ciba_order, take_pending_ciba_order
from app.ciba.service import ciba_service
from app.data.service import fake_data
from app.fga.client import FgaApiError
from app.fga.orders_access import ensure_owner_tuple_for_order

router = APIRouter()


class CibaStartRequest(BaseModel):
    binding_message: str | None = None


class CibaPollRequest(BaseModel):
    auth_req_id: str


class CibaAbandonRequest(BaseModel):
    auth_req_id: str


@router.post("/start")
async def start_ciba(request: CibaStartRequest, user: dict = Depends(get_current_user)):
    sub = user.get("sub", "")
    try:
        res = await ciba_service.start(
            login_hint=sub,
            scope="openid",
            binding_message=request.binding_message,
        )
        return {"status": "started", "auth_req_id": res.auth_req_id, "expires_in": res.expires_in, "interval": res.interval}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/poll")
async def poll_ciba(request: CibaPollRequest, user: dict = Depends(get_current_user)):
    sub = str(user.get("sub", "") or "")
    try:
        result = await ciba_service.poll(auth_req_id=request.auth_req_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    st = result.get("status")
    if st == "approved":
        pending = take_pending_ciba_order(request.auth_req_id, sub)
        if pending:
            try:
                order = fake_data.create_order(
                    product_id=str(pending["product_id"]),
                    buyer_sub=sub,
                    quantity=int(pending["quantity"]),
                    status="created",
                    company=pending.get("company"),
                    buyer_email=pending.get("buyer_email"),
                )
            except ValueError as e:
                result["order_create_error"] = str(e)
                return result
            try:
                await ensure_owner_tuple_for_order(sub, str(order["id"]))
                result["fga_owner"] = "ok"
            except FgaApiError as e:
                result["fga_owner"] = "failed"
                result["fga_owner_tuple_error"] = e.as_dict()
            result["order"] = order
        else:
            result["order_pending_notice"] = (
                "No pending checkout for this auth_req_id (already finalized, denied, or server was restarted)."
            )
    elif st == "denied":
        discard_pending_ciba_order(request.auth_req_id, sub)

    return result


@router.post("/pending/abandon")
async def abandon_pending_ciba(request: CibaAbandonRequest, user: dict = Depends(get_current_user)):
    """Drop a deferred checkout (e.g. client-side approval timeout)."""
    sub = str(user.get("sub", "") or "")
    discard_pending_ciba_order(request.auth_req_id, sub)
    return {"status": "abandoned", "auth_req_id": request.auth_req_id}

