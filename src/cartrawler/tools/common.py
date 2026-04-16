"""
Shared tool utilities
=====================
Helpers used by both car_tools and flight_tools to avoid duplication.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cartrawler.auth.jwt_handler import verify_token
from cartrawler.db.models import Booking, User


def booking_to_dict(b: Booking) -> dict:
    return {
        "booking_id":        b.booking_id,
        "user_id":           b.user_id,
        "booking_type":      b.booking_type,
        "flight_id":         getattr(b, "flight_id", None),
        "car_id":            b.car_id,
        "rental_days":       b.rental_days,
        "travel_date":       str(b.travel_date)       if b.travel_date       else None,
        "return_date":       str(b.return_date)       if b.return_date       else None,
        "flight_price":      getattr(b, "flight_price", None),
        "car_price":         b.car_price,
        "discount_applied":  b.discount_applied,
        "total_price":       b.total_price,
        "status":            b.status,
        "payment_status":    b.payment_status,
        "payment_method":    b.payment_method,
        "coupon_code":       b.coupon_code,
        "booking_date":      str(b.booking_date)      if getattr(b, "booking_date", None)      else None,
        "cancellation_date": str(b.cancellation_date) if getattr(b, "cancellation_date", None) else None,
    }


async def resolve_user(db: AsyncSession, access_token: str) -> User | None:
    try:
        payload = verify_token(access_token, expected_type="access")
    except ValueError:
        return None
    result = await db.execute(select(User).where(User.user_id == payload["sub"]))
    return result.scalar_one_or_none()


async def resolve_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Look up a user by email address — no token required."""
    result = await db.execute(select(User).where(User.email == email.lower().strip()))
    return result.scalar_one_or_none()


def update_loyalty_tier(user: User) -> None:
    pts = user.loyalty_points or 0
    if pts >= 10000:
        user.loyalty_tier = "PLATINUM"
    elif pts >= 5000:
        user.loyalty_tier = "GOLD"
    elif pts >= 1000:
        user.loyalty_tier = "SILVER"
    else:
        user.loyalty_tier = "BRONZE"
