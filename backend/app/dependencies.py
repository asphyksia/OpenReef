from fastapi import Cookie, Depends, Header, HTTPException, Request, Response, status
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User

COOKIE_NAME = "token"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


def clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


async def get_current_user(
    request: Request,
    token: str | None = Cookie(None, alias=COOKIE_NAME),
    csrf_token: str | None = Header(None, alias=CSRF_HEADER_NAME),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate user from httpOnly cookie + CSRF token.

    Reads JWT from httpOnly cookie and verifies CSRF via double-submit pattern
    for state-changing requests (POST, PUT, PATCH, DELETE).
    """
    if not token:
        raise _unauthorized()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise _unauthorized()
    except JWTError:
        raise _unauthorized()

    user = await db.get(User, user_id)
    if user is None:
        raise _unauthorized()

    # CSRF check for state-changing requests
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
        if not csrf_cookie or not csrf_token or csrf_cookie != csrf_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or mismatch",
            )

    return user


def _unauthorized():
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
