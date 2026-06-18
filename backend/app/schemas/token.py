"""
schemas/token.py — JWT token schemas

TokenResponse  — what /auth/login returns to the client
TokenData      — what we decode from the JWT payload internally
"""

from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: str | None = None