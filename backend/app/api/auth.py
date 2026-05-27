import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import clear_auth_cookies, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services import auth_service, credit_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

limiter = Limiter(key_func=get_remote_address)


@router.post("/register", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=body.email, password_hash=auth_service.hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = auth_service.create_access_token(str(user.id))
    csrf_token = secrets.token_hex(32)
    response.set_cookie(
        key="token", value=token, httponly=True, secure=False,
        samesite="lax", max_age=7 * 24 * 3600, path="/",
    )
    response.set_cookie(
        key="csrf_token", value=csrf_token, httponly=False,
        secure=False, samesite="lax", max_age=7 * 24 * 3600, path="/",
    )
    return {"message": "registered"}


@router.post("/login", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not auth_service.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = auth_service.create_access_token(str(user.id))
    csrf_token = secrets.token_hex(32)
    response.set_cookie(
        key="token", value=token, httponly=True, secure=False,
        samesite="lax", max_age=7 * 24 * 3600, path="/",
    )
    response.set_cookie(
        key="csrf_token", value=csrf_token, httponly=False,
        secure=False, samesite="lax", max_age=7 * 24 * 3600, path="/",
    )
    return {"message": "ok"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response):
    clear_auth_cookies(response)
    return {"message": "logged out"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    balance = await credit_service.get_balance(db, user.id)
    return UserResponse(id=user.id, email=user.email, is_verified=user.is_verified, balance=balance)
