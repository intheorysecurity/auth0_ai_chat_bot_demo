from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.provider import auth_provider

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected: Authorization: Bearer <access_token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    # Auth0 access tokens are JWTs when an API audience is requested.
    # If the token isn't JWT-shaped, we can fail fast with a clearer message.
    if token.count(".") != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authorization token is not a JWT. Ensure the frontend requests an Auth0 API access token "
                "by setting the correct audience (API Identifier)."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        claims = await auth_provider.validate_token(token)
        return claims
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
