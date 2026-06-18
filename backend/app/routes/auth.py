"""
routes/auth.py — Authentication endpoints

POST /auth/register  — create a new store owner account
POST /auth/login     — verify credentials, return JWT token
GET  /auth/me        — return the currently logged-in user's profile

The get_current_user dependency is defined here and reused across
every protected route in the app (uploads, analytics, AI, etc.).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Store  # noqa: F401 — Store must be imported to resolve relationships
from app.schemas.token import TokenResponse
from app.schemas.user import UserCreate, UserResponse, UserWithStoreResponse
from app.utils.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

router = APIRouter()

# OAuth2PasswordBearer tells FastAPI where the token comes from.
# Clients send: Authorization: Bearer <token>
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─── Dependency: get the current logged-in user ───────────────────────────────
# Any route that needs authentication adds:
#   current_user: User = Depends(get_current_user)

async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


# ─── POST /auth/register ──────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new store owner account",
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    # Check if email is already taken
    result = await db.execute(
        select(User).where(User.email == user_data.email.lower())
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    # Create new user
    new_user = User(
        email=user_data.email.lower(),
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
    )
    db.add(new_user)
    await db.flush()   # assigns the UUID without committing yet
    await db.refresh(new_user)

    return new_user


# ─── POST /auth/login ─────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT access token",
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncSession = Depends(get_db),
) -> dict:
    # OAuth2PasswordRequestForm uses "username" field — we treat it as email
    result = await db.execute(
        select(User).where(User.email == form_data.username.lower())
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    return {"access_token": access_token, "token_type": "bearer"}


# ─── GET /auth/me ─────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserWithStoreResponse,
    summary="Get the currently logged-in user's profile",
)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user