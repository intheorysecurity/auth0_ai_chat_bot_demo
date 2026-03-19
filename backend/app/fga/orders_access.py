"""Order visibility helpers: FGA off = demo sees all orders; FGA on = can_read enforced."""

from app.data.service import fake_data
from app.fga.client import fga_client


async def can_read_order(user_sub: str, order_id: str) -> bool:
    if not fga_client.is_configured():
        return True
    res = await fga_client.check(
        user=f"user:{user_sub}",
        relation="can_read",
        object=f"order:{order_id}",
    )
    return res.allowed


async def list_orders_for_principal(user_sub: str) -> list[dict]:
    """
    FGA not configured: return every seeded/synthetic order (demo catalog).
    FGA configured: only orders the user may read (owner or explicit viewer).
    """
    all_orders = fake_data.all_orders()
    if not fga_client.is_configured():
        return all_orders
    visible: list[dict] = []
    for o in all_orders:
        if await can_read_order(user_sub, str(o["id"])):
            visible.append(o)
    return visible


async def ensure_owner_tuple_for_order(buyer_sub: str, order_id: str) -> None:
    """
    Post-create FGA step: write `user:{buyer_sub} owner order:{order_id}`.

    Call this after every new order is persisted (REST, agent tool, or CIBA finalize
    in `/api/ciba/poll` after approval) so list/get/cancel can enforce `can_read` / `can_write`.
    No-op when FGA is not configured.
    """
    if not fga_client.is_configured():
        return
    await fga_client.write_tuples(
        writes=[
            {
                "user": f"user:{buyer_sub}",
                "relation": "owner",
                "object": f"order:{order_id}",
            }
        ]
    )
