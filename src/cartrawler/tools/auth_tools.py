"""
MCP Auth Tools
==============
Tools:
  - register_user   → create new account
  - login_user      → authenticate and receive JWT tokens
  - refresh_tokens  → exchange refresh token for new access token
  - get_profile     → fetch current user profile (requires token)
  - logout_user     → invalidate refresh token
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cartrawler.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    verify_token,
)
from cartrawler.auth.password import hash_password, verify_password
from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import User


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _next_user_id(existing_ids: list[str]) -> str:
    """Generate next sequential U1xxx ID."""
    if not existing_ids:
        return "U1101"
    nums = [int(uid[1:]) for uid in existing_ids if uid.startswith("U")]
    return f"U{max(nums) + 1}"


def _user_to_dict(user: User) -> dict:
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "age": user.age,
        "gender": user.gender,
        "home_city": user.home_city,
        "preferred_airline": user.preferred_airline,
        "preferred_car_type": user.preferred_car_type,
        "loyalty_tier": user.loyalty_tier,
        "loyalty_points": user.loyalty_points,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: register_user
# ─────────────────────────────────────────────────────────────────────────────

async def register_user(
    name: str,
    email: str,
    password: str,
    phone: str | None = None,
    age: int | None = None,
    gender: str | None = None,
    home_city: str | None = None,
    preferred_airline: str | None = None,
    preferred_car_type: str | None = None,
) -> dict:
    """
    Register a new user account.

    Returns: {"success": bool, "message": str, "user_id": str | None,
              "tokens": TokenPair | None}
    """
    async with AsyncSessionLocal() as db:
        # Check email uniqueness
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            return {
                "success": False,
                "message": f"Email '{email}' is already registered. Please log in.",
                "user_id": None,
                "tokens": None,
            }

        # Generate user_id
        all_ids_result = await db.execute(select(User.user_id))
        all_ids = [row[0] for row in all_ids_result.fetchall()]
        user_id = _next_user_id(all_ids)

        # Create user
        hashed = hash_password(password)
        user = User(
            user_id=user_id,
            name=name,
            email=email,
            hashed_password=hashed,
            phone=phone,
            age=age,
            gender=gender,
            home_city=home_city,
            preferred_airline=preferred_airline,
            preferred_car_type=preferred_car_type,
            nationality="Indian",
            loyalty_tier="BRONZE",
            loyalty_points=0,
            is_active=True,
            is_verified=False,
        )

        # Issue tokens
        access = create_access_token(
            subject=user_id,
            extra={"name": name, "email": email, "tier": "BRONZE"},
        )
        refresh = create_refresh_token(subject=user_id)
        user.refresh_token = refresh

        db.add(user)
        await db.commit()

        return {
            "success": True,
            "message": f"Account created successfully! Welcome, {name}.",
            "user_id": user_id,
            "tokens": {
                "access_token": access,
                "refresh_token": refresh,
                "token_type": "bearer",
                "user_id": user_id,
                "name": name,
                "loyalty_tier": "BRONZE",
                "loyalty_points": 0,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: login_user
# ─────────────────────────────────────────────────────────────────────────────

async def login_user(email: str, password: str) -> dict:
    """
    Authenticate a user with email + password.

    Returns: {"success": bool, "message": str, "tokens": TokenPair | None}
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user: User | None = result.scalar_one_or_none()

        if not user:
            return {
                "success": False,
                "message": "No account found with that email address.",
                "tokens": None,
            }

        if not user.hashed_password:
            return {
                "success": False,
                "message": (
                    "This account was imported and has no password set. "
                    "Please reset your password."
                ),
                "tokens": None,
            }

        if not verify_password(password, user.hashed_password):
            return {
                "success": False,
                "message": "Incorrect password. Please try again.",
                "tokens": None,
            }

        if not user.is_active:
            return {
                "success": False,
                "message": "Your account has been deactivated. Contact support.",
                "tokens": None,
            }

        # Issue new tokens
        access = create_access_token(
            subject=user.user_id,
            extra={
                "name": user.name,
                "email": user.email,
                "tier": user.loyalty_tier,
            },
        )
        refresh = create_refresh_token(subject=user.user_id)
        user.refresh_token = refresh
        await db.commit()

        return {
            "success": True,
            "message": f"Welcome back, {user.name}! You are now logged in.",
            "tokens": {
                "access_token": access,
                "refresh_token": refresh,
                "token_type": "bearer",
                "user_id": user.user_id,
                "name": user.name,
                "loyalty_tier": user.loyalty_tier,
                "loyalty_points": user.loyalty_points,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: refresh_tokens
# ─────────────────────────────────────────────────────────────────────────────

async def refresh_tokens(refresh_token: str) -> dict:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    """
    try:
        payload = verify_token(refresh_token, expected_type="refresh")
    except ValueError as exc:
        return {"success": False, "message": str(exc), "tokens": None}

    user_id: str = payload["sub"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.user_id == user_id))
        user: User | None = result.scalar_one_or_none()

        if not user or user.refresh_token != refresh_token:
            return {
                "success": False,
                "message": "Refresh token is no longer valid. Please log in again.",
                "tokens": None,
            }

        new_access = create_access_token(
            subject=user_id,
            extra={"name": user.name, "tier": user.loyalty_tier},
        )
        new_refresh = create_refresh_token(subject=user_id)
        user.refresh_token = new_refresh
        await db.commit()

        return {
            "success": True,
            "message": "Tokens refreshed.",
            "tokens": {
                "access_token": new_access,
                "refresh_token": new_refresh,
                "token_type": "bearer",
                "user_id": user_id,
                "name": user.name,
                "loyalty_tier": user.loyalty_tier,
                "loyalty_points": user.loyalty_points,
            },
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_profile
# ─────────────────────────────────────────────────────────────────────────────

async def get_profile(access_token: str) -> dict:
    """Fetch the authenticated user's profile using their access token."""
    try:
        payload = verify_token(access_token, expected_type="access")
    except ValueError as exc:
        return {"success": False, "message": str(exc), "profile": None}

    user_id: str = payload["sub"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.user_id == user_id))
        user: User | None = result.scalar_one_or_none()

        if not user:
            return {"success": False, "message": "User not found.", "profile": None}

        return {
            "success": True,
            "message": "Profile fetched successfully.",
            "profile": _user_to_dict(user),
        }


async def get_profile_by_email(email: str) -> dict:
    """Fetch a user's profile by email — no token required."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email.lower().strip()))
        user: User | None = result.scalar_one_or_none()
        if not user:
            return {"success": False, "message": f"No account found for {email}.", "profile": None}
        return {"success": True, "profile": _user_to_dict(user)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: logout_user
# ─────────────────────────────────────────────────────────────────────────────

async def logout_user(access_token: str) -> dict:
    """Invalidate the user's refresh token (server-side logout)."""
    try:
        payload = verify_token(access_token, expected_type="access")
    except ValueError as exc:
        return {"success": False, "message": str(exc)}

    user_id: str = payload["sub"]

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.user_id == user_id))
        user: User | None = result.scalar_one_or_none()
        if user:
            user.refresh_token = None
            await db.commit()

    return {"success": True, "message": "Logged out successfully."}
