import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import clear_auth_cookies, get_current_user
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.user import UserResponse
from app.services import auth_service, credit_service, email_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


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

    if settings.email_verification_enabled:
        verification_token = auth_service.create_verification_token(str(user.id))
        email_sent = await email_service.send_verification_email(user.email, verification_token)
        if not email_sent:
            logger.warning("Failed to send verification email to %s", user.email)
        return {"message": "registered", "email_sent": email_sent, "verification_required": True}

    return {"message": "registered", "verification_required": False}


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

    if settings.email_verification_enabled and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please check your inbox or request a new verification link.",
        )

    token = auth_service.create_access_token(str(user.id))
    csrf_token = secrets.token_hex(32)
    response.set_cookie(
        key="token", value=token, httponly=True, secure=settings.cookie_secure,
        samesite="lax", max_age=settings.cookie_max_age, path="/",
    )
    response.set_cookie(
        key="csrf_token", value=csrf_token, httponly=False,
        secure=settings.cookie_secure, samesite="lax", max_age=settings.cookie_max_age, path="/",
    )
    return {"message": "ok"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(response: Response, _: User = Depends(get_current_user)):
    clear_auth_cookies(response)
    return {"message": "logged out"}


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    balance = await credit_service.get_balance(db, user.id)
    return UserResponse(id=user.id, email=user.email, is_verified=user.is_verified, balance=balance)


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    token = body.get("token", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token is required")

    user_id = auth_service.decode_verification_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified"}

    user.is_verified = True
    await db.commit()
    return {"message": "Email verified successfully"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    email = body.get("email", "")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.is_verified:
        return {"message": "Email already verified"}

    verification_token = auth_service.create_verification_token(str(user.id))
    email_sent = await email_service.send_verification_email(user.email, verification_token)
    if not email_sent:
        logger.warning("Failed to resend verification email to %s", user.email)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send email")

    return {"message": "Verification email sent"}
