# Demo store data

## Products (remote)

At startup the backend **GETs** **`PRODUCT_CATALOG_URL`** (default **`https://fakestoreapi.com/products`**) and maps each item to the internal product shape:

| Remote (Fake Store) | Internal field |
|---------------------|----------------|
| `id` | `id` (string) |
| `title` | `name` |
| `price` (USD float) | `price_cents` |
| `category` | single entry in `tags` |
| `image` | `image_url` |
| `rating.count` | `inventory_count` (fallback **100** if missing) |

Override the URL in `backend/.env` if you host a compatible JSON array (same field names as [Fake Store products](https://fakestoreapi.com/docs)).

**Startup requires network** when using the default URL.

## Optional seed orders (`seed_orders.json`)

To pre-populate in-memory orders (e.g. FGA demos), add **`app/data/catalogs/seed_orders.json`**:

```json
{
  "seed_orders": [
    {
      "id": "seed-1",
      "product_id": "1",
      "buyer_sub": "auth0|example-user",
      "status": "created",
      "quantity": 1,
      "created_days_ago": 7,
      "company": "Optional Co",
      "buyer_email": "buyer@example.com"
    }
  ]
}
```

- Every **`product_id`** must exist in the **fetched** product list (Fake Store uses **`"1"`** … **`"20"`**).
- **`created_days_ago`**: optional if **`created_at`** (Unix seconds) is set.
- **`status`**: `created`, `cancelled`, or `pending_approval` (demo).
- Omit **`total_cents`** to use **`price_cents × quantity`** from the product.

## Local images (optional)

Create **`backend/app/data/catalogs/assets/`** and add files; the API mounts them at **`GET /catalog-assets/<relative-path>`** when that directory exists (e.g. `http://localhost:8000/catalog-assets/sku/photo.png`). Fake Store already provides remote **`image`** URLs, so this folder is usually omitted. In production, use your API’s public origin in `image_url`, or any **https** CDN URL.
