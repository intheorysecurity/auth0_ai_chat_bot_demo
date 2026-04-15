from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config import settings
from app.data.service import fake_data
from app.fga.client import FgaApiError, fga_client
from app.fga.orders_access import (
    can_read_order,
    ensure_owner_tuple_for_order,
    list_orders_for_principal,
)

router = APIRouter()


def _fga_denied_detail(
    message: str, *, user: str, relation: str, object: str
) -> dict:
    return {
        "message": message,
        "fga_check": {
            "allowed": False,
            "user": user,
            "relation": relation,
            "object": object,
        },
    }


class CreateOrderRequest(BaseModel):
    product_id: str
    quantity: int = 1
    company: str | None = None


@router.get("/products")
async def list_products(
    user: dict = Depends(get_current_user),
    limit: int | None = Query(None, ge=1),
):
    cap = settings.product_list_max_limit
    default = settings.product_list_default_limit
    eff = min(limit if limit is not None else default, cap)
    eff = max(1, eff)
    rows = fake_data.list_products(limit=eff)
    return {
        "products": rows,
        "total": fake_data.product_total_count(),
        "returned": len(rows),
    }


@router.get("/products/{product_id}")
async def get_product(product_id: str, user: dict = Depends(get_current_user)):
    p = fake_data.get_product(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product": p}


@router.get("/orders")
async def list_orders(user: dict = Depends(get_current_user)):
    sub = user.get("sub", "")
    try:
        orders = await list_orders_for_principal(sub)
        return {"orders": orders}
    except FgaApiError as e:
        raise HTTPException(
            status_code=502,
            detail={"context": "list_orders", **e.as_dict()},
        ) from e


@router.get("/orders/{order_id}")
async def get_order(order_id: str, user: dict = Depends(get_current_user)):
    o = fake_data.get_order(order_id)
    if not o:
        raise HTTPException(status_code=404, detail="Order not found")
    sub = user.get("sub", "")
    if fga_client.is_configured():
        try:
            allowed = await can_read_order(sub, order_id)
        except FgaApiError as e:
            raise HTTPException(
                status_code=502,
                detail={"context": "get_order_can_read", **e.as_dict()},
            ) from e
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail=_fga_denied_detail(
                    "Not authorized to view this order",
                    user=f"user:{sub}",
                    relation="can_read",
                    object=f"order:{order_id}",
                ),
            )
    return {"order": o}


@router.post("/orders")
async def create_order(request: CreateOrderRequest, user: dict = Depends(get_current_user)):
    sub = user.get("sub", "")
    email = user.get("email")
    if isinstance(email, str):
        buyer_email = email
    else:
        buyer_email = None
    try:
        order = fake_data.create_order(
            product_id=request.product_id,
            buyer_sub=sub,
            quantity=request.quantity,
            company=request.company,
            buyer_email=buyer_email,
        )
        try:
            await ensure_owner_tuple_for_order(sub, str(order["id"]))
        except FgaApiError as e:
            raise HTTPException(
                status_code=502,
                detail={
                    "context": "create_order_write_owner_tuple",
                    "order": order,
                    **e.as_dict(),
                },
            ) from e
        return {"order": order}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: str, user: dict = Depends(get_current_user)):
    sub = user.get("sub", "")
    if fga_client.is_configured():
        try:
            res = await fga_client.check(
                user=f"user:{sub}",
                relation="can_write",
                object=f"order:{order_id}",
            )
        except FgaApiError as e:
            raise HTTPException(
                status_code=502,
                detail={"context": "cancel_order_check", **e.as_dict()},
            ) from e
        if not res.allowed:
            raise HTTPException(
                status_code=403,
                detail=_fga_denied_detail(
                    "Not authorized to cancel this order",
                    user=f"user:{sub}",
                    relation="can_write",
                    object=f"order:{order_id}",
                ),
            )
    try:
        order = fake_data.cancel_order(order_id)
        return {"order": order}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

