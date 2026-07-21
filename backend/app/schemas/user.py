"""
schemas/user.py — Pydantic schemas for User and Store

Schemas serve two purposes:
  1. Input validation  — FastAPI rejects requests that don't match the shape
  2. Response shaping  — controls exactly which fields the API returns
                         (e.g. hashed_password is NEVER included in responses)

Pattern:
  UserBase       — shared fields
  UserCreate     — fields required to register (includes password)
  UserResponse   — fields safe to return in API responses (no password)
  StoreCreate    — fields to create a store
  StoreResponse  — fields safe to return for a store
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── User schemas ─────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Basic password rules — extend later with zxcvbn if needed."""
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class UserResponse(UserBase):
    id: uuid.UUID
    is_active: bool
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}  # allows ORM → Pydantic conversion


# ─── Store schemas ────────────────────────────────────────────────────────────

class StoreCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    pos_system: str | None = Field(
        default=None,
        description="POS system name (e.g. AdvEntPOS, Square, Clover)",
    )


class StoreUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    phone: str | None = None
    pos_system: str | None = None


class StoreResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: str | None
    city: str | None
    state: str | None
    zip_code: str | None
    phone: str | None
    pos_system: str | None
    # Phase 14: the security key other stores enter to add us as an exchange
    # partner. Shown in the Transfers tab.
    exchange_code: str | None = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Combined response (user + their store) ───────────────────────────────────

class UserWithStoreResponse(UserResponse):
    """
    Phase 14: `store` = the CURRENTLY SELECTED store (kept for backward compat),
    `stores` = all stores this user can access (owner: all owned; staff: just
    their assigned store), `role` = owner | staff.
    """
    role: str = "owner"
    store: StoreResponse | None = None
    stores: list[StoreResponse] = []

    model_config = {"from_attributes": True}


# ─── Staff management (Phase 14) ──────────────────────────────────────────────

class StaffCreate(BaseModel):
    """Owner creates a staff login pinned to one store."""
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8, max_length=100)


class StaffResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    store_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}