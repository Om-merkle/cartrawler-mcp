"""
MCP Offer / Discount Tools
============================
Tools:
  - get_applicable_offers  → fetch all applicable coupons for a booking scenario
  - validate_coupon        → validate a specific coupon code
  - get_all_offers         → list all active offers
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select

from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import Offer


def _offer_to_dict(o: Offer) -> dict:
    return {
        "offer_id": o.offer_id,
        "coupon_code": o.coupon_code,
        "trigger_event": o.trigger_event,
        "description": o.description,
        "discount_percentage": o.discount_percentage,
        "max_discount_amount": o.max_discount_amount,
        "min_booking_amount": o.min_booking_amount,
        "valid_city": o.valid_city,
        "applicable_on": o.applicable_on,
        "valid_from": str(o.valid_from) if o.valid_from else None,
        "valid_till": str(o.valid_till) if o.valid_till else None,
        "is_active": o.is_active,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_all_offers
# ─────────────────────────────────────────────────────────────────────────────

async def get_all_offers(
    applicable_on: str | None = None,  # FLIGHT / CAR / BOTH
    city: str | None = None,
    active_only: bool = True,
) -> dict:
    """
    List all available discount offers / coupons.

    Args:
        applicable_on: Filter by what the offer applies to (FLIGHT/CAR/BOTH)
        city: Filter by city (or ALL)
        active_only: Only return currently active offers
    """
    async with AsyncSessionLocal() as db:
        conditions = []
        today = date.today()

        if active_only:
            conditions.append(Offer.is_active == True)  # noqa: E712
            conditions.append(Offer.valid_till >= today)

        if applicable_on:
            conditions.append(
                or_(
                    Offer.applicable_on == applicable_on.upper(),
                    Offer.applicable_on == "BOTH",
                )
            )

        if city:
            conditions.append(
                or_(Offer.valid_city == "ALL", Offer.valid_city.ilike(f"%{city}%"))
            )

        query = select(Offer)
        if conditions:
            query = query.where(and_(*conditions))
        query = query.order_by(Offer.discount_percentage.desc())

        result = await db.execute(query)
        offers = result.scalars().all()

        return {
            "success": True,
            "count": len(offers),
            "offers": [_offer_to_dict(o) for o in offers],
            "message": f"Found {len(offers)} active offer(s).",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: validate_coupon
# ─────────────────────────────────────────────────────────────────────────────

async def validate_coupon(
    coupon_code: str,
    booking_amount: float,
    applicable_on: str = "BOTH",   # FLIGHT / CAR / BOTH
    city: str | None = None,
) -> dict:
    """
    Validate a coupon code and compute the discount for a given booking amount.

    Args:
        coupon_code: The coupon code string (e.g. "FIRST20", "COMBO10")
        booking_amount: Total booking amount before discount (INR)
        applicable_on: Whether this is for a FLIGHT, CAR, or BOTH
        city: City to validate location-specific coupons
    """
    async with AsyncSessionLocal() as db:
        today = date.today()

        conditions = [
            Offer.coupon_code == coupon_code.upper(),
            Offer.is_active == True,  # noqa: E712
            Offer.valid_till >= today,
            or_(
                Offer.applicable_on == applicable_on.upper(),
                Offer.applicable_on == "BOTH",
            ),
        ]

        if city:
            conditions.append(
                or_(Offer.valid_city == "ALL", Offer.valid_city.ilike(f"%{city}%"))
            )

        result = await db.execute(select(Offer).where(and_(*conditions)))
        offer: Offer | None = result.scalar_one_or_none()

        if not offer:
            return {
                "success": False,
                "valid": False,
                "message": (
                    f"Coupon '{coupon_code}' is not valid for this booking. "
                    "It may be expired, incorrect, or not applicable."
                ),
                "discount_amount": 0,
                "final_amount": booking_amount,
            }

        if booking_amount < offer.min_booking_amount:
            return {
                "success": False,
                "valid": False,
                "message": (
                    f"Coupon '{coupon_code}' requires a minimum booking amount of "
                    f"INR {offer.min_booking_amount:,.2f}. "
                    f"Your amount (INR {booking_amount:,.2f}) is below the threshold."
                ),
                "discount_amount": 0,
                "final_amount": booking_amount,
            }

        discount = min(
            booking_amount * offer.discount_percentage / 100,
            offer.max_discount_amount,
        )
        final = round(booking_amount - discount, 2)

        return {
            "success": True,
            "valid": True,
            "coupon_code": offer.coupon_code,
            "description": offer.description,
            "discount_percentage": offer.discount_percentage,
            "discount_amount": round(discount, 2),
            "max_discount_cap": offer.max_discount_amount,
            "original_amount": booking_amount,
            "final_amount": final,
            "message": (
                f"Coupon applied! You save INR {discount:,.2f} "
                f"({offer.discount_percentage}% off). Final price: INR {final:,.2f}."
            ),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_applicable_offers
# ─────────────────────────────────────────────────────────────────────────────

async def get_applicable_offers(
    booking_amount: float,
    applicable_on: str = "BOTH",
    city: str | None = None,
    is_first_booking: bool = False,
    loyalty_tier: str = "BRONZE",
) -> dict:
    """
    Get all applicable offers for a given booking scenario and compute savings.

    Args:
        booking_amount: Base booking amount (INR)
        applicable_on: FLIGHT / CAR / BOTH
        city: Travel city (for location-specific offers)
        is_first_booking: Whether this is the user's first booking
        loyalty_tier: User's loyalty tier (BRONZE/SILVER/GOLD/PLATINUM)
    """
    async with AsyncSessionLocal() as db:
        today = date.today()

        result = await db.execute(
            select(Offer).where(
                and_(
                    Offer.is_active == True,  # noqa: E712
                    Offer.valid_till >= today,
                    Offer.min_booking_amount <= booking_amount,
                    or_(
                        Offer.applicable_on == applicable_on.upper(),
                        Offer.applicable_on == "BOTH",
                    ),
                    or_(
                        Offer.valid_city == "ALL",
                        *(
                            [Offer.valid_city.ilike(f"%{city}%")]
                            if city
                            else []
                        ),
                    ),
                )
            )
        )
        all_offers = result.scalars().all()

        applicable = []
        for offer in all_offers:
            # First-booking filter
            if offer.trigger_event == "FIRST_BOOKING" and not is_first_booking:
                continue
            # Loyalty tier filter
            if offer.trigger_event == "LOYALTY_GOLD" and loyalty_tier not in ("GOLD", "PLATINUM"):
                continue
            if offer.trigger_event == "LOYALTY_PLATINUM" and loyalty_tier != "PLATINUM":
                continue

            discount = min(
                booking_amount * offer.discount_percentage / 100,
                offer.max_discount_amount,
            )
            applicable.append({
                **_offer_to_dict(offer),
                "computed_discount": round(discount, 2),
                "final_amount": round(booking_amount - discount, 2),
            })

        # Sort by highest computed discount
        applicable.sort(key=lambda x: x["computed_discount"], reverse=True)

        best = applicable[0] if applicable else None

        return {
            "success": True,
            "count": len(applicable),
            "offers": applicable,
            "best_offer": best,
            "message": (
                f"Found {len(applicable)} applicable offer(s). "
                + (
                    f"Best: '{best['coupon_code']}' saves INR {best['computed_discount']:,.2f}."
                    if best
                    else "No applicable offers found for this booking."
                )
            ),
        }
