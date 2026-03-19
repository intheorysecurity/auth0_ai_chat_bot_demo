# Sample FGA authorization model

This folder contains an **OpenFGA / Auth0 FGA** authorization model that matches what the chat bot backend expects for **simulated orders**.

## What the app uses

| Tuple / check | When |
|---------------|------|
| `user:{sub} owner order:{id}` | Written when an order is created (`POST /api/data/orders`, `create_order` tool). **Not** auto-written for in-memory seed orders — add those tuples in FGA yourself if you want them visible under FGA. |
| `user:{sub} viewer order:{id}` | Optional: grant **read-only** access (not written by the app unless you add it in FGA) |
| `check(user:{sub}, can_read, order:{id})` | **List orders** / **get order** / `list_orders` / `get_order` tool when FGA is configured |
| `check(user:{sub}, can_write, order:{id})` | **Cancel order** / `cancel_order` tool when FGA is configured |
| `check_permission` tool | Calls FGA with whatever `relation` and `object` you pass (e.g. `can_read`, `order:seed-1`) |

User IDs are Auth0 subjects (`sub`), prefixed as OpenFGA users: `user:{sub}`.

### Demo behavior

- **FGA not configured:** `GET /api/data/orders` returns **all** in-memory demo orders (including other users’ past orders). `GET /api/data/orders/{id}` returns any existing order. Cancels are not FGA-enforced.
- **FGA configured:** only orders where `can_read` passes appear in the list; a single order returns **403** if the user cannot read it. Seed orders are visible only if you define matching tuples in FGA (or turn FGA off for a full demo list).

## Files

- **`authorization-model.fga`** — OpenFGA DSL (schema 1.1). Copy or use as-is.

## Option A: Auth0 Fine-Grained Authorization (hosted)

1. In the [Auth0 Dashboard](https://manage.auth0.com), open **Authorization** → **FGA** (or your FGA product path).
2. Create a **store** if you don’t have one.
3. Add an **authorization model** — paste the contents of `authorization-model.fga`, or import the equivalent JSON if your UI supports it.
4. Note **API URL** (region-specific, e.g. `https://api.us1.fga.dev`), **Store ID**, and **Authorization Model ID** after publish.
5. Create credentials the API can use (static token and/or client credentials for the FGA API audience).
6. Set `backend/.env` — see the main repo **README** FGA section and `backend/.env.example`.

## Option B: OpenFGA CLI (self-hosted or cloud)

Install the [OpenFGA CLI](https://github.com/openfga/cli), then:

```bash
# Create a store (if needed) and note the store id from the response
fga store create --name ai-chat-bot-demo

# Write this model to that store (replace STORE_ID)
fga model write --store-id=STORE_ID --file=authorization-model.fga
```

The command prints an **authorization model id** — put that in `FGA_MODEL_ID` in `backend/.env`.

### Optional: JSON for HTTP API

If you need JSON instead of DSL:

```bash
fga model transform --file=authorization-model.fga
```

Use the output with `POST /stores/{store_id}/authorization-models` per [OpenFGA API docs](https://openfga.dev/docs).

## Try it without FGA

If you do **not** set `FGA_API_URL` / `FGA_STORE_ID` (and credentials), the app still runs: **all** demo orders appear in `GET /api/data/orders`; get/cancel are not FGA-enforced.

## Try it with FGA

1. Apply the model to your store.
2. Fill in `backend/.env` FGA variables and restart the backend.
3. **List orders** as your real user — you should only see orders where you are **owner** (or **viewer** if you add tuples manually).
4. Open `GET /api/data/orders/{id}` for another user’s seeded order id — expect **403** when FGA is on.
5. Ask the assistant to cancel **another user’s** order — expect **403** / `not_authorized` on cancel.
