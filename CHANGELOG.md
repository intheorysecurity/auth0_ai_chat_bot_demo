# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **Demo catalog:** products now load from **`PRODUCT_CATALOG_URL`** (default [Fake Store](https://fakestoreapi.com/products)) instead of per-vertical `retail.json` / `healthcare.json`. Optional seed orders: `catalogs/seed_orders.json` only.
- **Repo layout:** removed unused Next.js starter SVGs, duplicate `backend/requirements.txt` (install via **`pip install -e .`** / **`pip install -e ".[dev]"`** from `backend/`), optional `catalogs/assets/` README-only folder, and merged docs image notes into **`docs/README.md`** / **`SCREENSHOTS.md`**. Declared **`aiosqlite`** and **`certifi`** in **`pyproject.toml`** with **`[tool.hatch.build.targets.wheel]`** for Docker/`pip install`.

### Added

- **Product `image_url`** from remote `image` (or `/catalog-assets/...` if you use local assets). Order/list tooling includes **`product_image_url`** where relevant.

### Fixed

- **OpenAI provider:** Function/tool `parameters` JSON Schemas are normalized so every `type: "object"` includes a `properties` object (empty `{}` when there are no arguments). This avoids OpenAI API `400` errors such as `invalid_function_parameters` / “object schema missing properties” for built-in tools like `whoami`, `list_orders`, and `list_products`, and for MCP tools with the same pattern ([`backend/app/llm/openai_provider.py`](backend/app/llm/openai_provider.py)).

## [Earlier]

Prior work (Auth0, FGA, CIBA deferred checkout, Ollama tool IDs, FGA write body without empty `deletes`, docs, and initial GitHub publish) predates this changelog file.
