"""
MCP Flight Tools
================
Tools:
  - search_flights       → find available flights by route/date/class
  - get_flight_details   → detailed info for a specific flight_id
  - book_flight          → create a flight booking (requires auth token)
  - get_booking_details  → retrieve booking by booking_id (requires auth)
  - cancel_booking       → cancel a booking (requires auth)
  - list_my_bookings     → list all bookings for authenticated user
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from cartrawler.auth.jwt_handler import verify_token
from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import Booking, Flight, Offer, User


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _flight_to_dict(f: Flight) -> dict:
    return {
        "flight_id": f.flight_id,
        "airline": f.airline,
        "flight_number": f.flight_number,
        "source": f.source,
        "source_city": f.source_city,
        "destination": f.destination,
        "destination_city": f.destination_city,
        "departure_time": f.departure_time,
        "arrival_time": f.arrival_time,
        "duration_mins": f.duration_mins,
        "price_economy": f.price_economy,
        "price_business": f.price_business,
        "stops": f.stops,
        "aircraft": f.aircraft,
        "available_seats": f.available_seats,
        "baggage_kg": f.baggage_kg,
        "refundable": f.refundable,
        "meal_included": f.meal_included,
        "wifi_available": f.wifi_available,
    }


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


def _next_booking_id(existing: list[str]) -> str:
    if not existing:
        return "B7301"
    nums = [int(bid[1:]) for bid in existing if bid.startswith("B")]
    return f"B{max(nums) + 1}"


async def _resolve_user(db: AsyncSession, access_token: str) -> User | None:
    try:
        payload = verify_token(access_token, expected_type="access")
    except ValueError:
        return None
    result = await db.execute(select(User).where(User.user_id == payload["sub"]))
    return result.scalar_one_or_none()


# ─────────────────────────────────────────────────────────────────────────────
# Tool: search_flights
# ─────────────────────────────────────────────────────────────────────────────

async def search_flights(
    source: str | None = None,
    destination: str | None = None,
    source_city: str | None = None,
    destination_city: str | None = None,
    cabin_class: str = "Economy",  # Economy | Business
    max_price: float | None = None,
    max_stops: int | None = None,
    airline: str | None = None,
    refundable_only: bool = False,
    limit: int = 20,
) -> dict:
    """
    Search for available flights. Accepts IATA codes or city names.

    Args:
        source: IATA code (e.g. "DEL") — takes precedence over source_city
        destination: IATA code (e.g. "BOM")
        source_city: City name fallback (e.g. "New Delhi")
        destination_city: City name fallback (e.g. "Mumbai")
        cabin_class: "Economy" or "Business"
        max_price: Filter by maximum price (in INR)
        max_stops: 0 = direct only, 1 = max 1 stop, etc.
        airline: Filter by airline name
        refundable_only: Return only refundable flights
        limit: Max results (default 20)
    """
    async with AsyncSessionLocal() as db:
        conditions = []

        if source:
            conditions.append(Flight.source == source.upper())
        elif source_city:
            conditions.append(Flight.source_city.ilike(f"%{source_city}%"))

        if destination:
            conditions.append(Flight.destination == destination.upper())
        elif destination_city:
            conditions.append(Flight.destination_city.ilike(f"%{destination_city}%"))

        if max_stops is not None:
            conditions.append(Flight.stops <= max_stops)

        if airline:
            conditions.append(Flight.airline.ilike(f"%{airline}%"))

        if refundable_only:
            conditions.append(Flight.refundable == True)  # noqa: E712

        price_col = Flight.price_business if cabin_class == "Business" else Flight.price_economy
        if max_price:
            conditions.append(price_col <= max_price)

        query = select(Flight)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(price_col).limit(limit)

        result = await db.execute(query)
        flights = result.scalars().all()

        if not flights:
            return {
                "success": True,
                "count": 0,
                "flights": [],
                "message": "No flights found matching your criteria. Try relaxing filters.",
            }

        return {
            "success": True,
            "count": len(flights),
            "cabin_class": cabin_class,
            "flights": [_flight_to_dict(f) for f in flights],
            "message": f"Found {len(flights)} flight(s).",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_flight_details
# ─────────────────────────────────────────────────────────────────────────────

async def get_flight_details(flight_id: str) -> dict:
    """Get complete details for a specific flight by its ID (e.g. F4001)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Flight).where(Flight.flight_id == flight_id.upper()))
        flight = result.scalar_one_or_none()

        if not flight:
            return {"success": False, "message": f"Flight '{flight_id}' not found.", "flight": None}

        return {"success": True, "flight": _flight_to_dict(flight)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: book_flight
# ─────────────────────────────────────────────────────────────────────────────

async def book_flight(
    access_token: str,
    flight_id: str,
    travel_date: str,        # ISO date: YYYY-MM-DD
    cabin_class: str = "Economy",
    payment_method: str = "CARD",  # CARD | UPI | WALLET | NET_BANKING
    coupon_code: str | None = None,
) -> dict:
    """
    Book a flight for the authenticated user.

    Requires a valid access_token from login_user or register_user.
    Returns booking confirmation with booking_id.
    """
    async with AsyncSessionLocal() as db:
        # Auth
        user = await _resolve_user(db, access_token)
        if not user:
            return {
                "success": False,
                "message": "Authentication required. Please log in first.",
                "booking": None,
            }

        # Fetch flight
        r = await db.execute(select(Flight).where(Flight.flight_id == flight_id.upper()))
        flight: Flight | None = r.scalar_one_or_none()
        if not flight:
            return {
                "success": False,
                "message": f"Flight '{flight_id}' not found.",
                "booking": None,
            }

        if flight.available_seats < 1:
            return {
                "success": False,
                "message": f"No seats available on flight {flight_id}.",
                "booking": None,
            }

        # Price
        price = flight.price_business if cabin_class == "Business" else flight.price_economy

        # Apply coupon if provided
        discount = 0.0
        if coupon_code:
            coupon_result = await db.execute(
                select(Offer).where(
                    and_(
                        Offer.coupon_code == coupon_code.upper(),
                        Offer.is_active == True,  # noqa: E712
                        or_(Offer.applicable_on == "BOTH", Offer.applicable_on == "FLIGHT"),
                    )
                )
            )
            offer: Offer | None = coupon_result.scalar_one_or_none()
            if offer and price >= offer.min_booking_amount:
                discount = min(price * offer.discount_percentage / 100, offer.max_discount_amount)

        total = round(price - discount, 2)

        # Generate booking ID
        all_ids_r = await db.execute(select(Booking.booking_id))
        all_ids = [row[0] for row in all_ids_r.fetchall()]
        booking_id = _next_booking_id(all_ids)

        # Parse date
        try:
            t_date = date.fromisoformat(travel_date)
        except ValueError:
            return {"success": False, "message": f"Invalid date format: '{travel_date}'. Use YYYY-MM-DD.", "booking": None}

        booking = Booking(
            booking_id=booking_id,
            user_id=user.user_id,
            booking_type="FLIGHT_ONLY",
            flight_id=flight.flight_id,
            flight_price=price,
            travel_date=t_date,
            discount_applied=discount,
            total_price=total,
            status="CONFIRMED",
            payment_status="PAID",
            payment_method=payment_method.upper(),
            coupon_code=coupon_code.upper() if coupon_code else None,
            booking_date=date.today(),
        )

        # Decrement seat count
        flight.available_seats -= 1

        # Award loyalty points (1 point per INR 100)
        points_earned = int(total / 100)
        user.loyalty_points = (user.loyalty_points or 0) + points_earned
        _update_loyalty_tier(user)

        db.add(booking)
        await db.commit()

        return {
            "success": True,
            "message": (
                f"Flight booked successfully! Booking ID: {booking_id}. "
                f"You earned {points_earned} loyalty points."
            ),
            "booking": _booking_to_dict(booking),
            "points_earned": points_earned,
        }


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
    access_token: str,
    status_filter: str | None = None,   # PENDING/CONFIRMED/CANCELLED/COMPLETED
    booking_type: str | None = None,     # FLIGHT_ONLY/CAR_ONLY/COMBO
    limit: int = 20,
) -> dict:
    """List all bookings for the authenticated user with optional filters."""
    async with AsyncSessionLocal() as db:
        user = await _resolve_user(db, access_token)
        if not user:
            return {"success": False, "message": "Authentication required.", "bookings": []}

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

async def cancel_booking(access_token: str, booking_id: str) -> dict:
    """Cancel a booking and process refund if eligible."""
    async with AsyncSessionLocal() as db:
        user = await _resolve_user(db, access_token)
        if not user:
            return {"success": False, "message": "Authentication required."}

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

        # Determine refund
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
                f"Refund of INR {booking.total_price:,.2f} will be credited "
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


# ─────────────────────────────────────────────────────────────────────────────
# Internal: Loyalty Tier Update
# ─────────────────────────────────────────────────────────────────────────────

def _update_loyalty_tier(user: User) -> None:
    pts = user.loyalty_points or 0
    if pts >= 10000:
        user.loyalty_tier = "PLATINUM"
    elif pts >= 5000:
        user.loyalty_tier = "GOLD"
    elif pts >= 1000:
        user.loyalty_tier = "SILVER"
    else:
        user.loyalty_tier = "BRONZE"
