from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from app.config import settings

_CATALOG_DIR = Path(__file__).resolve().parent / "catalogs"


@dataclass
class Product:
    id: str
    name: str
    price_cents: int
    inventory_count: int
    tags: list[str]
    # From remote catalog (e.g. Fake Store `image`); or `/catalog-assets/...` for local files
    image_url: str = ""


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


def _product_from_fakestore_item(item: dict, index: int) -> Product:
    if not isinstance(item, dict):
        raise ValueError(f"products[{index}] must be an object")
    pid_raw = item.get("id")
    if pid_raw is None:
        raise ValueError(f"products[{index}] missing id")
    pid = str(int(pid_raw)) if isinstance(pid_raw, (int, float)) else str(pid_raw).strip()
    if not pid:
        raise ValueError(f"products[{index}] missing id")

    title = item.get("title")
    if title is None or not str(title).strip():
        raise ValueError(f"products[{pid}] missing title")
    name = str(title).strip()

    price = item.get("price")
    if price is None:
        raise ValueError(f"products[{pid}] missing price")
    price_cents = int(round(float(price) * 100))

    rating = item.get("rating")
    if isinstance(rating, dict) and "count" in rating:
        inventory_count = max(0, int(rating["count"]))
    else:
        inventory_count = 100

    category = item.get("category")
    tags = [str(category).strip()] if category is not None and str(category).strip() else []

    img = item.get("image")
    image_url = str(img).strip() if img is not None else ""

    return Product(
        id=pid,
        name=name,
        price_cents=price_cents,
        inventory_count=inventory_count,
        tags=tags,
        image_url=image_url,
    )


def _load_seed_orders(raw: dict, products: dict[str, Product]) -> dict[str, Order]:
    seed = raw.get("seed_orders")
    if seed is None:
        return {}
    if not isinstance(seed, list):
        raise ValueError("'seed_orders' must be an array when present")

    now = time.time()
    orders: dict[str, Order] = {}
    for i, item in enumerate(seed):
        if not isinstance(item, dict):
            raise ValueError(f"seed_orders[{i}] must be an object")
        oid = str(item["id"]).strip()
        if not oid:
            raise ValueError(f"seed_orders[{i}] missing id")
        if oid in orders:
            raise ValueError(f"Duplicate seed order id: {oid}")
        pid = str(item["product_id"]).strip()
        if pid not in products:
            raise ValueError(
                f"seed_orders[{oid}] references unknown product_id {pid!r}"
            )
        qty = int(item["quantity"])
        total = item.get("total_cents")
        if total is None:
            total = products[pid].price_cents * qty
        else:
            total = int(total)
        created = item.get("created_at")
        if created is not None:
            created_at = float(created)
        else:
            days = float(item.get("created_days_ago", 0))
            created_at = now - 86400 * days
        auth_req = item.get("auth_req_id")
        orders[oid] = Order(
            id=oid,
            product_id=pid,
            buyer_sub=str(item["buyer_sub"]),
            status=str(item.get("status", "created")),
            quantity=qty,
            total_cents=total,
            created_at=created_at,
            auth_req_id=str(auth_req) if auth_req else None,
            company=str(item.get("company", "") or ""),
            buyer_email=str(item.get("buyer_email", "") or ""),
        )
    return orders


def load_catalog_for_settings() -> tuple[dict[str, Product], dict[str, Order]]:
    url = str(settings.product_catalog_url).strip()
    if not url:
        raise ValueError("product_catalog_url / PRODUCT_CATALOG_URL is empty")

    with httpx.Client(timeout=30.0) as client:
        try:
            response = client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise RuntimeError(
                f"Failed to load product catalog from {url!r}: {e}"
            ) from e
        data = response.json()

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError(
            f"Catalog URL must return a non-empty JSON array; got {type(data).__name__}"
        )

    products: dict[str, Product] = {}
    for i, item in enumerate(data):
        p = _product_from_fakestore_item(item, i)
        if p.id in products:
            raise ValueError(f"Duplicate product id: {p.id}")
        products[p.id] = p

    orders: dict[str, Order] = {}
    seed_path = _CATALOG_DIR / "seed_orders.json"
    if seed_path.is_file():
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Catalog seed file {seed_path.name} must be a JSON object")
        orders = _load_seed_orders(raw, products)

    return products, orders


class FakeDataStore:
    def __init__(self) -> None:
        self._products: dict[str, Product] = {}
        self._orders: dict[str, Order] = {}
        self._seed()

    def _seed(self) -> None:
        self._products, self._orders = load_catalog_for_settings()

    def list_products(self, limit: int | None = None) -> list[dict]:
        rows = [asdict(p) for p in self._products.values()]
        if limit is not None:
            rows = rows[: max(0, limit)]
        return rows

    def product_total_count(self) -> int:
        return len(self._products)

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
