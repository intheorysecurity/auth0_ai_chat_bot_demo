from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, asdict


@dataclass
class Product:
    id: str
    name: str
    price_cents: int
    inventory_count: int
    tags: list[str]


@dataclass
class Order:
    id: str
    product_id: str
    buyer_sub: str
    status: str  # created|pending_approval|cancelled
    quantity: int
    total_cents: int
    created_at: float
    auth_req_id: str | None = None
    company: str = ""
    buyer_email: str = ""


class FakeDataStore:
    def __init__(self) -> None:
        self._products: dict[str, Product] = {}
        self._orders: dict[str, Order] = {}
        self._seed()

    def _seed(self) -> None:
        products = [
            Product(id="1", name="Gemma Plush", price_cents=1999, inventory_count=50, tags=["demo", "plush"]),
            Product(id="2", name="MCP Card Deck", price_cents=2499, inventory_count=25, tags=["demo", "cards"]),
        ]
        self._products = {p.id: p for p in products}

        now = time.time()
        # Past demo orders (FGA off: everyone sees all; FGA on: only if can_read, e.g. owner tuple for buyer_sub).
        self._orders = {
            "seed-1": Order(
                id="seed-1",
                product_id="1",
                buyer_sub="auth0|other-user",
                status="created",
                quantity=1,
                total_cents=1999,
                created_at=now - 86400 * 45,
                company="Cobalt Freight & Logistics",
                buyer_email="marisol.vega@cobaltfreight.example",
            ),
            "seed-2": Order(
                id="seed-2",
                product_id="2",
                buyer_sub="auth0|other-user",
                status="cancelled",
                quantity=2,
                total_cents=4998,
                created_at=now - 86400 * 30,
                company="Cobalt Freight & Logistics",
                buyer_email="derrick.poole@cobaltfreight.example",
            ),
            "seed-3": Order(
                id="seed-3",
                product_id="1",
                buyer_sub="auth0|other-user",
                status="created",
                quantity=3,
                total_cents=5997,
                created_at=now - 86400 * 14,
                company="Northwind Data Labs",
                buyer_email="yuki.tan@northwindlabs.example",
            ),
            "seed-4": Order(
                id="seed-4",
                product_id="2",
                buyer_sub="auth0|demo-colleague",
                status="created",
                quantity=1,
                total_cents=2499,
                created_at=now - 86400 * 7,
                company="Harborline Retail Group",
                buyer_email="amara.okonkwo@harborline.example",
            ),
            "seed-5": Order(
                id="seed-5",
                product_id="1",
                buyer_sub="auth0|demo-colleague",
                status="created",
                quantity=1,
                total_cents=1999,
                created_at=now - 86400 * 2,
                company="Summit Circuit Supply",
                buyer_email="james.rutherford@summitcircuit.example",
            ),
        }

    def list_products(self) -> list[dict]:
        return [asdict(p) for p in self._products.values()]

    def get_product(self, product_id: str) -> dict | None:
        p = self._products.get(product_id)
        return asdict(p) if p else None

    def list_orders_for_user(self, user_sub: str) -> list[dict]:
        return [asdict(o) for o in self._orders.values() if o.buyer_sub == user_sub]

    def all_orders(self) -> list[dict]:
        """All orders, newest first (for demo list when FGA is off, or as input for FGA filtering)."""
        rows = [asdict(o) for o in self._orders.values()]
        rows.sort(key=lambda r: float(r.get("created_at", 0)), reverse=True)
        return rows

    def get_order(self, order_id: str) -> dict | None:
        o = self._orders.get(order_id)
        return asdict(o) if o else None

    def create_order(
        self,
        product_id: str,
        buyer_sub: str,
        quantity: int,
        status: str = "created",
        auth_req_id: str | None = None,
        company: str | None = None,
        buyer_email: str | None = None,
    ) -> dict:
        p = self._products.get(product_id)
        if not p:
            raise ValueError("Unknown product_id")
        if quantity <= 0:
            raise ValueError("quantity must be > 0")

        order_id = f"order-{uuid.uuid4().hex[:10]}"
        total = p.price_cents * quantity
        co = (company or "").strip() or "Personal"
        em = (buyer_email or "").strip()
        if not em:
            em = f"buyer-{uuid.uuid4().hex[:10]}@orders.demo.local"
        o = Order(
            id=order_id,
            product_id=product_id,
            buyer_sub=buyer_sub,
            status=status,
            quantity=quantity,
            total_cents=total,
            created_at=time.time(),
            auth_req_id=auth_req_id,
            company=co,
            buyer_email=em,
        )
        self._orders[o.id] = o
        return asdict(o)

    def cancel_order(self, order_id: str) -> dict:
        o = self._orders.get(order_id)
        if not o:
            raise ValueError("Unknown order_id")
        o.status = "cancelled"
        o.auth_req_id = None
        self._orders[o.id] = o
        return asdict(o)

    def mark_order_created(self, order_id: str) -> dict:
        o = self._orders.get(order_id)
        if not o:
            raise ValueError("Unknown order_id")
        o.status = "created"
        o.auth_req_id = None
        self._orders[o.id] = o
        return asdict(o)


fake_data = FakeDataStore()

