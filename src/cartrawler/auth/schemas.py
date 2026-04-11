"""Pydantic schemas for auth request/response bodies."""
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Payload for POST /auth/register."""

    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    phone: str | None = None
    age: int | None = Field(default=None, ge=18, le=120)
    gender: str | None = None
    home_city: str | None = None
    preferred_airline: str | None = None
    preferred_car_type: str | None = None


class UserLogin(BaseModel):
    """Payload for POST /auth/login."""

    email: EmailStr
    password: str


class TokenPair(BaseModel):
    """Returned on successful login or token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    loyalty_tier: str
    loyalty_points: int


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    """Safe user representation (no password)."""

    user_id: str
    name: str
    email: str
    phone: str | None
    age: int | None
    gender: str | None
    nationality: str | None
    preferred_car_type: str | None
    preferred_airline: str | None
    home_city: str | None
    loyalty_tier: str
    loyalty_points: int
    is_active: bool
    is_verified: bool

    model_config = {"from_attributes": True}


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)
