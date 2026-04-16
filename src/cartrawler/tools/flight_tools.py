"""
Booking Tools (shared)
======================
Functions used by the MCP server for booking management:
  - get_booking_details  → retrieve a booking by ID (requires auth)
  - cancel_booking       → cancel a booking (requires auth)
  - list_my_bookings     → list all bookings for authenticated user
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import Booking, Flight, User
from cartrawler.tools.common import resolve_user, resolve_user_by_email, update_loyalty_tier


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _booking_to_dict(b: Booking) -> dict:
    return {
        "booking_id": b.booking_id,
        "user_id": b.user_id,
        "booking_type": b.booking_type,
        "flight_id": b.flight_id,
        "car_id": b.car_id,
        "rental_days": b.rental_days,
        "travel_date": str(b.travel_date) if b.travel_date else None,
        "return_date": str(b.return_date) if b.return_date else None,
        "flight_price": b.flight_price,
        "car_price": b.car_price,
        "discount_applied": b.discount_applied,
        "total_price": b.total_price,
        "status": b.status,
        "payment_status": b.payment_status,
        "payment_method": b.payment_method,
        "coupon_code": b.coupon_code,
        "booking_date": str(b.booking_date) if b.booking_date else None,
        "cancellation_date": str(b.cancellation_date) if b.cancellation_date else None,
    }


async def _resolve_user(db: AsyncSession, access_token: str) -> User | None:
    return await resolve_user(db, access_token)


async def _resolve_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await resolve_user_by_email(db, email)


def _update_loyalty_tier(user: User) -> None:
    update_loyalty_tier(user)


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_booking_details
# ─────────────────────────────────────────────────────────────────────────────

async def get_booking_details(access_token: str, booking_id: str) -> dict:
    """Retrieve full details of a specific booking (must belong to the user)."""
    async with AsyncSessionLocal() as db:
        user = await _resolve_user(db, access_token)
        if not user:
            return {"success": False, "message": "Authentication required.", "booking": None}

        r = await db.execute(
            select(Booking).where(
                and_(Booking.booking_id == booking_id, Booking.user_id == user.user_id)
            )
        )
        booking: Booking | None = r.scalar_one_or_none()
        if not booking:
            return {
                "success": False,
                "message": f"Booking '{booking_id}' not found for your account.",
                "booking": None,
            }

        return {"success": True, "booking": _booking_to_dict(booking)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: list_my_bookings
# ─────────────────────────────────────────────────────────────────────────────

async def list_my_bookings(
    email: str,
    status_filter: str | None = None,
    booking_type: str | None = None,
    limit: int = 20,
) -> dict:
    """List all bookings for the user identified by email."""
    async with AsyncSessionLocal() as db:
        user = await _resolve_user_by_email(db, email)
        if not user:
            return {"success": False, "message": f"No account found for {email}.", "bookings": []}

        conditions = [Booking.user_id == user.user_id]
        if status_filter:
            conditions.append(Booking.status == status_filter.upper())
        if booking_type:
            conditions.append(Booking.booking_type == booking_type.upper())

        r = await db.execute(
            select(Booking)
            .where(and_(*conditions))
            .order_by(Booking.created_at.desc())
            .limit(limit)
        )
        bookings = r.scalars().all()

        return {
            "success": True,
            "count": len(bookings),
            "bookings": [_booking_to_dict(b) for b in bookings],
            "message": f"Found {len(bookings)} booking(s) for {user.name}.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: cancel_booking
# ─────────────────────────────────────────────────────────────────────────────

async def cancel_booking(email: str, booking_id: str) -> dict:
    """Cancel a booking and process refund if eligible."""
    async with AsyncSessionLocal() as db:
        user = await _resolve_user_by_email(db, email)
        if not user:
            return {"success": False, "message": f"No account found for {email}."}

        r = await db.execute(
            select(Booking).where(
                and_(Booking.booking_id == booking_id, Booking.user_id == user.user_id)
            )
        )
        booking: Booking | None = r.scalar_one_or_none()
        if not booking:
            return {"success": False, "message": f"Booking '{booking_id}' not found."}

        if booking.status in ("CANCELLED", "COMPLETED"):
            return {
                "success": False,
                "message": f"Booking is already {booking.status}. Cannot cancel.",
            }

        booking.status = "CANCELLED"
        booking.cancellation_date = date.today()

        # Determine refund eligibility
        refund_eligible = False
        refund_message = "Non-refundable booking — no refund issued."

        if booking.flight_id:
            r2 = await db.execute(select(Flight).where(Flight.flight_id == booking.flight_id))
            flight = r2.scalar_one_or_none()
            if flight and flight.refundable:
                refund_eligible = True
        else:
            refund_eligible = True  # Car-only bookings are refundable by default

        if refund_eligible:
            booking.payment_status = "REFUNDED"
            refund_message = (
                f"Refund of {booking.total_price:,.2f} will be credited "
                "to the original payment source within 5-7 business days."
            )

        # Restore seat if flight booking
        if booking.flight_id:
            r3 = await db.execute(select(Flight).where(Flight.flight_id == booking.flight_id))
            f = r3.scalar_one_or_none()
            if f:
                f.available_seats += 1

        await db.commit()

        return {
            "success": True,
            "message": f"Booking {booking_id} cancelled. {refund_message}",
            "booking_id": booking_id,
            "refund_eligible": refund_eligible,
        }
