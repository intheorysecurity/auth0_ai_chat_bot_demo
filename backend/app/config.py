from pathlib import Path

from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    # Auth
    auth_provider: str = "auth0"  # "auth0" or "okta"
    auth0_domain: str = ""
    auth0_audience: str = ""
    okta_issuer: str = ""
    okta_audience: str = ""

    # LLM
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ollama_base_url: str = "http://localhost:11434"
    ollama_default_model: str = ""

    # Persistence
    database_url: str = "sqlite:///./app.db"

    # Auth0 FGA / OpenFGA
    fga_api_url: str = ""
    fga_store_id: str = ""
    fga_model_id: str = ""
    # Either provide a static API token...
    fga_api_token: str = ""
    # ...or provide client-credentials wrapper settings:
    fga_api_token_issuer: str = ""
    fga_api_audience: str = ""
    fga_client_id: str = ""
    fga_client_secret: str = ""

    # Auth0 CIBA (Backchannel Authentication)
    auth0_issuer_url: str = ""  # e.g. https://YOUR_TENANT.us.auth0.com/
    auth0_ciba_client_id: str = ""
    auth0_ciba_client_secret: str = ""
    # Optional override endpoints (otherwise derived from issuer):
    auth0_ciba_authorization_endpoint: str = ""  # e.g. https://.../bc-authorize
    auth0_ciba_token_endpoint: str = ""  # e.g. https://.../oauth/token
    # Optional: used by some tenants to scope issued tokens
    auth0_ciba_audience: str = ""

    # App
    frontend_url: str = "http://localhost:3000"
    # Simulated store: GET this URL at startup; must return a JSON array of products
    # (default: Fake Store API). Optional seed orders: app/data/catalogs/seed_orders.json
    product_catalog_url: str = "https://fakestoreapi.com/products"
    # Cap list responses (HTTP GET /api/data/products + list_products tool default)
    product_list_default_limit: int = 8
    product_list_max_limit: int = 20

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


settings = Settings()
