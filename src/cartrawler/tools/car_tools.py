"""
MCP Car / Vehicle Rental Tools
================================
CarTrawler-aligned tool suite for vehicle search and booking.

CarTrawler Guidelines respected:
  - Minimum rental age: 21 (luxury/SUV: 25)
  - Refundable security deposit collected at pickup
  - Cancellation ≥2 hrs before pickup = full refund
  - Insurance optional; base price excludes fuel
  - Unlimited-km for Zoomcar/Revv/CarTrawler vendors

Tools:
  - search_cars          → find available rental cars by city/type/date
  - get_car_details      → full info for a specific car_id
  - book_car             → reserve a car (requires auth)
  - search_rides         → search existing ride bookings / plans
  - get_ride_details     → detailed ride info by booking_id
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select

from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import Booking, Car, Offer, User
from cartrawler.tools.common import resolve_user, update_loyalty_tier


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _car_to_dict(c: Car) -> dict:
    return {
        "car_id": c.car_id,
        "vendor": c.vendor,
        "city": c.city,
        "pickup_location": c.pickup_location,
        "car_type": c.car_type,
        "car_model": c.car_model,
        "fuel_type": c.fuel_type,
        "transmission": c.transmission,
        "seating_capacity": c.seating_capacity,
        "price_per_day": c.price_per_day,
        "price_per_hour": c.price_per_hour,
        "with_driver": c.with_driver,
        "availability": c.availability,
        "rating": c.rating,
        "total_reviews": c.total_reviews,
        "ac": c.ac,
        "insurance_included": c.insurance_included,
        "min_age_required": c.min_age_required,
    }


def _booking_to_dict(b: Booking) -> dict:
    return {
        "booking_id": b.booking_id,
        "user_id": b.user_id,
        "booking_type": b.booking_type,
        "car_id": b.car_id,
        "rental_days": b.rental_days,
        "travel_date": str(b.travel_date) if b.travel_date else None,
        "return_date": str(b.return_date) if b.return_date else None,
        "car_price": b.car_price,
        "discount_applied": b.discount_applied,
        "total_price": b.total_price,
        "status": b.status,
        "payment_status": b.payment_status,
        "payment_method": b.payment_method,
        "coupon_code": b.coupon_code,
    }


def _next_booking_id(existing: list[str]) -> str:
    nums = [int(bid[1:]) for bid in existing if bid.startswith("B")]
    return f"B{max(nums) + 1}" if nums else "B7301"


async def _resolve_user(db, access_token: str):
    return await resolve_user(db, access_token)


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


# ─────────────────────────────────────────────────────────────────────────────
# Tool: search_cars
# ─────────────────────────────────────────────────────────────────────────────

async def search_cars(
    city: str,
    car_type: str | None = None,       # Sedan/SUV/Hatchback/Luxury/MUV/Compact
    fuel_type: str | None = None,       # Petrol/Diesel/Electric/CNG
    transmission: str | None = None,    # Manual/Automatic
    with_driver: bool | None = None,
    max_price_per_day: float | None = None,
    vendor: str | None = None,
    min_rating: float | None = None,
    insurance_included: bool | None = None,
    available_only: bool = True,
    limit: int = 20,
) -> dict:
    """
    Search available rental cars in a given city.

    CarTrawler policy note: Minimum driver age 21 years.
    Security deposit (INR 2,000-10,000) collected at pickup.
    Fuel is NOT included unless stated.

    Args:
        city: Target city (e.g. "Mumbai", "New Delhi", "Goa")
        car_type: Vehicle category filter
        fuel_type: Fuel preference
        transmission: Manual or Automatic
        with_driver: Filter for chauffeur-driven options
        max_price_per_day: Budget ceiling per day (INR)
        vendor: Preferred vendor (Zoomcar/Revv/Savaari/Avis/Hertz etc.)
        min_rating: Minimum star rating (e.g. 4.0)
        insurance_included: Filter for cars with insurance included
        available_only: Show only available cars (default True)
        limit: Max results
    """
    async with AsyncSessionLocal() as db:
        conditions = [Car.city.ilike(f"%{city}%")]

        if car_type:
            conditions.append(Car.car_type.ilike(f"%{car_type}%"))
        if fuel_type:
            conditions.append(Car.fuel_type.ilike(f"%{fuel_type}%"))
        if transmission:
            conditions.append(Car.transmission.ilike(f"%{transmission}%"))
        if with_driver is not None:
            conditions.append(Car.with_driver == with_driver)
        if max_price_per_day is not None:
            conditions.append(Car.price_per_day <= max_price_per_day)
        if vendor:
            conditions.append(Car.vendor.ilike(f"%{vendor}%"))
        if min_rating is not None:
            conditions.append(Car.rating >= min_rating)
        if insurance_included is not None:
            conditions.append(Car.insurance_included == insurance_included)
        if available_only:
            conditions.append(Car.availability == True)  # noqa: E712

        query = (
            select(Car)
            .where(and_(*conditions))
            .order_by(Car.rating.desc(), Car.price_per_day)
            .limit(limit)
        )
        result = await db.execute(query)
        cars = result.scalars().all()

        if not cars:
            return {
                "success": True,
                "count": 0,
                "city": city,
                "cars": [],
                "message": f"No cars found in {city} matching your criteria.",
                "policy_note": (
                    "CarTrawler policy: Min driver age 21. "
                    "Security deposit collected at pickup. Fuel not included."
                ),
            }

        return {
            "success": True,
            "count": len(cars),
            "city": city,
            "cars": [_car_to_dict(c) for c in cars],
            "policy_note": (
                "Min driver age: 21 years. Security deposit: INR 2,000-10,000 at pickup. "
                "Fuel NOT included. Cancellation ≥2 hrs before pickup = full refund."
            ),
            "message": f"Found {len(cars)} car(s) in {city}.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_car_details
# ─────────────────────────────────────────────────────────────────────────────

async def get_car_details(car_id: str) -> dict:
    """Get complete details for a specific car by ID (e.g. C5001)."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Car).where(Car.car_id == car_id.upper()))
        car = result.scalar_one_or_none()
        if not car:
            return {"success": False, "message": f"Car '{car_id}' not found.", "car": None}
        return {"success": True, "car": _car_to_dict(car)}


# ─────────────────────────────────────────────────────────────────────────────
# Tool: book_car
# ─────────────────────────────────────────────────────────────────────────────

async def book_car(
    access_token: str,
    car_id: str,
    pickup_date: str,         # YYYY-MM-DD
    rental_days: int,          # number of days
    payment_method: str = "CARD",
    coupon_code: str | None = None,
) -> dict:
    """
    Book a rental car for the authenticated user.

    CarTrawler policy: Minimum rental age 21. Fuel not included.
    Security deposit collected at pickup (not charged here).
    """
    if rental_days < 1:
        return {"success": False, "message": "Rental days must be at least 1.", "booking": None}

    async with AsyncSessionLocal() as db:
        user = await _resolve_user(db, access_token)
        if not user:
            return {
                "success": False,
                "message": "Authentication required. Please log in first.",
                "booking": None,
            }

        # Age validation
        if user.age and user.age < 21:
            return {
                "success": False,
                "message": (
                    f"Minimum driver age is 21 years. "
                    f"Your registered age ({user.age}) does not meet the requirement."
                ),
                "booking": None,
            }

        # Fetch car
        r = await db.execute(select(Car).where(Car.car_id == car_id.upper()))
        car: Car | None = r.scalar_one_or_none()
        if not car:
            return {"success": False, "message": f"Car '{car_id}' not found.", "booking": None}

        if not car.availability:
            return {
                "success": False,
                "message": f"Car '{car_id}' is currently not available.",
                "booking": None,
            }

        # Luxury/SUV age check
        if car.car_type in ("Luxury", "SUV") and user.age and user.age < 25:
            return {
                "success": False,
                "message": (
                    f"Luxury and SUV vehicles require a minimum age of 25. "
                    f"Your registered age is {user.age}."
                ),
                "booking": None,
            }

        # Parse dates
        try:
            p_date = date.fromisoformat(pickup_date)
        except ValueError:
            return {
                "success": False,
                "message": f"Invalid pickup date: '{pickup_date}'. Use YYYY-MM-DD.",
                "booking": None,
            }

        from datetime import timedelta
        return_date = p_date + timedelta(days=rental_days)

        # Price
        base_price = car.price_per_day * rental_days

        # Apply coupon
        discount = 0.0
        if coupon_code:
            coupon_r = await db.execute(
                select(Offer).where(
                    and_(
                        Offer.coupon_code == coupon_code.upper(),
                        Offer.is_active == True,  # noqa: E712
                        or_(Offer.applicable_on == "BOTH", Offer.applicable_on == "CAR"),
                        or_(Offer.valid_city == "ALL", Offer.valid_city.ilike(f"%{car.city}%")),
                    )
                )
            )
            offer: Offer | None = coupon_r.scalar_one_or_none()
            if offer and base_price >= offer.min_booking_amount:
                discount = min(
                    base_price * offer.discount_percentage / 100,
                    offer.max_discount_amount,
                )

        total = round(base_price - discount, 2)

        # Generate booking ID
        all_ids_r = await db.execute(select(Booking.booking_id))
        all_ids = [row[0] for row in all_ids_r.fetchall()]
        booking_id = _next_booking_id(all_ids)

        booking = Booking(
            booking_id=booking_id,
            user_id=user.user_id,
            booking_type="CAR_ONLY",
            car_id=car.car_id,
            rental_days=rental_days,
            car_price=base_price,
            travel_date=p_date,
            return_date=return_date,
            discount_applied=discount,
            total_price=total,
            status="CONFIRMED",
            payment_status="PAID",
            payment_method=payment_method.upper(),
            coupon_code=coupon_code.upper() if coupon_code else None,
            booking_date=date.today(),
        )

        # Mark car unavailable
        car.availability = False

        # Loyalty points
        points_earned = int(total / 100)
        user.loyalty_points = (user.loyalty_points or 0) + points_earned
        _update_loyalty_tier(user)

        db.add(booking)
        await db.commit()

        return {
            "success": True,
            "message": (
                f"Car booked! Booking ID: {booking_id}. "
                f"Pickup: {pickup_date} | Return: {return_date}. "
                f"Total: INR {total:,.2f}. "
                f"Earned {points_earned} loyalty points. "
                f"Note: A security deposit will be collected at pickup. Fuel not included."
            ),
            "booking": _booking_to_dict(booking),
            "points_earned": points_earned,
            "security_deposit_note": "A refundable security deposit of INR 2,000-10,000 is required at vehicle pickup.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: search_rides
# ─────────────────────────────────────────────────────────────────────────────

async def search_rides(
    access_token: str,
    city: str | None = None,
    travel_date: str | None = None,    # YYYY-MM-DD
    status_filter: str | None = None,  # CONFIRMED/PENDING/COMPLETED/CANCELLED
    limit: int = 20,
) -> dict:
    """
    Search all ride (car) bookings for the authenticated user.

    Covers: airport pickup/drop, hotel transfers, local city travel — everything
    stored under CAR_ONLY or COMBO bookings with a car_id.
    """
    async with AsyncSessionLocal() as db:
        user = await _resolve_user(db, access_token)
        if not user:
            return {"success": False, "message": "Authentication required.", "rides": []}

        conditions = [
            Booking.user_id == user.user_id,
            or_(Booking.booking_type == "CAR_ONLY", Booking.booking_type == "COMBO"),
            Booking.car_id.isnot(None),
        ]

        if status_filter:
            conditions.append(Booking.status == status_filter.upper())
        if travel_date:
            try:
                td = date.fromisoformat(travel_date)
                conditions.append(Booking.travel_date == td)
            except ValueError:
                pass

        r = await db.execute(
            select(Booking)
            .where(and_(*conditions))
            .order_by(Booking.travel_date.desc())
            .limit(limit)
        )
        bookings = r.scalars().all()

        # Enrich with car info
        rides = []
        for b in bookings:
            ride = _booking_to_dict(b)
            if b.car_id:
                car_r = await db.execute(select(Car).where(Car.car_id == b.car_id))
                car = car_r.scalar_one_or_none()
                if car:
                    ride["car_info"] = {
                        "vendor": car.vendor,
                        "city": car.city,
                        "car_type": car.car_type,
                        "car_model": car.car_model,
                        "pickup_location": car.pickup_location,
                        "with_driver": car.with_driver,
                    }
            rides.append(ride)

        return {
            "success": True,
            "count": len(rides),
            "rides": rides,
            "message": f"Found {len(rides)} ride booking(s) for {user.name}.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_ride_details
# ─────────────────────────────────────────────────────────────────────────────

async def get_ride_details(access_token: str, booking_id: str) -> dict:
    """
    Get complete ride/car booking details including vehicle info,
    pickup location, dates, pricing, and status.
    """
    async with AsyncSessionLocal() as db:
        user = await _resolve_user(db, access_token)
        if not user:
            return {"success": False, "message": "Authentication required.", "ride": None}

        r = await db.execute(
            select(Booking).where(
                and_(Booking.booking_id == booking_id, Booking.user_id == user.user_id)
            )
        )
        booking: Booking | None = r.scalar_one_or_none()
        if not booking or not booking.car_id:
            return {
                "success": False,
                "message": f"Ride booking '{booking_id}' not found.",
                "ride": None,
            }

        ride = _booking_to_dict(booking)

        # Fetch car details
        car_r = await db.execute(select(Car).where(Car.car_id == booking.car_id))
        car = car_r.scalar_one_or_none()
        if car:
            ride["car_info"] = _car_to_dict(car)

        return {
            "success": True,
            "ride": ride,
            "message": "Ride details retrieved successfully.",
        }
