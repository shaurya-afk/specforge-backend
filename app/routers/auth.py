import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_oauth_state_token,
    hash_password,
    verify_oauth_state_token,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.services.google_oauth import build_authorization_url, exchange_code_for_userinfo

router = APIRouter(prefix="/auth", tags=["auth"])


def _google_redirect_uri(request: Request) -> str:
    return str(request.base_url) + "auth/google/callback"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> UserOut:
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(email=body.email, hashed_password=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if (
        user is None
        or user.hashed_password is None
        or not verify_password(body.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token({"sub": user.email})
    return TokenResponse(access_token=token)


@router.get("/google/login")
async def google_login(request: Request) -> RedirectResponse:
    state = create_oauth_state_token()
    redirect_uri = _google_redirect_uri(request)
    return RedirectResponse(build_authorization_url(redirect_uri, state))


@router.get("/google/callback")
async def google_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    frontend_url = get_settings().FRONTEND_URL.rstrip("/")

    if error is not None:
        return RedirectResponse(f"{frontend_url}/auth/callback?error={error}")

    if state is None or not verify_oauth_state_token(state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state")

    if code is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing authorization code")

    redirect_uri = _google_redirect_uri(request)
    try:
        userinfo = await exchange_code_for_userinfo(code, redirect_uri)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Google authentication failed: {exc}")

    result = await db.execute(select(User).where(User.google_id == userinfo.sub))
    user = result.scalar_one_or_none()

    if user is None:
        result = await db.execute(select(User).where(User.email == userinfo.email))
        user = result.scalar_one_or_none()
        if user is not None:
            user.google_id = userinfo.sub
        else:
            user = User(email=userinfo.email, hashed_password=None, google_id=userinfo.sub)
            db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token({"sub": user.email})
    return RedirectResponse(f"{frontend_url}/auth/callback?token={token}")
