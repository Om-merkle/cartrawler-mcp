"""
MCP Hotel Search Tools
=======================
Hotels are linked to destination cities served by flights.
If no real hotel API is configured, the tool falls back to the
stub data seeded from city → flight destination mapping.

Tools:
  - search_hotels   → find hotels by city, area, rating, price
  - get_hotel_details → full hotel info by hotel_id
"""
from __future__ import annotations

from sqlalchemy import and_, select

from cartrawler.db.database import AsyncSessionLocal
from cartrawler.db.models import Hotel

# City aliases — normalises variations like "Delhi" → "New Delhi"
CITY_ALIASES: dict[str, str] = {
    "delhi": "New Delhi",
    "new delhi": "New Delhi",
    "bombay": "Mumbai",
    "mumbai": "Mumbai",
    "bengaluru": "Bengaluru",
    "bangalore": "Bengaluru",
    "blr": "Bengaluru",
    "chennai": "Chennai",
    "madras": "Chennai",
    "hyderabad": "Hyderabad",
    "kolkata": "Kolkata",
    "calcutta": "Kolkata",
    "pune": "Pune",
    "goa": "Goa",
    "jaipur": "Jaipur",
    "ahmedabad": "Ahmedabad",
}


def _normalise_city(city: str) -> str:
    return CITY_ALIASES.get(city.lower().strip(), city.strip())


def _hotel_to_dict(h: Hotel) -> dict:
    return {
        "hotel_id": h.hotel_id,
        "name": h.name,
        "city": h.city,
        "area": h.area,
        "address": h.address,
        "star_rating": h.star_rating,
        "price_per_night": h.price_per_night,
        "amenities": h.amenities,
        "total_rooms": h.total_rooms,
        "available_rooms": h.available_rooms,
        "check_in_time": h.check_in_time,
        "check_out_time": h.check_out_time,
        "image_url": h.image_url,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: search_hotels
# ─────────────────────────────────────────────────────────────────────────────

async def search_hotels(
    city: str,
    area: str | None = None,
    min_rating: float | None = None,
    max_price_per_night: float | None = None,
    min_rooms_required: int = 1,
    amenities: list[str] | None = None,   # e.g. ["wifi", "pool"]
    limit: int = 20,
) -> dict:
    """
    Search hotels at a flight destination by city, area, rating or price.

    Covers airport vicinity, city centre, and popular localities.
    Useful for building a complete travel itinerary (flight + car + hotel).

    Args:
        city: Destination city name or IATA alias (e.g. "Mumbai", "DEL")
        area: Specific area / locality (e.g. "Bandra", "Connaught Place")
        min_rating: Minimum star rating (1-5)
        max_price_per_night: Budget ceiling per night (INR)
        min_rooms_required: Minimum available rooms needed
        amenities: Required amenities (wifi/pool/gym/spa/restaurant etc.)
        limit: Max results
    """
    city_norm = _normalise_city(city)

    async with AsyncSessionLocal() as db:
        conditions = [
            Hotel.city.ilike(f"%{city_norm}%"),
            Hotel.is_active == True,  # noqa: E712
            Hotel.available_rooms >= min_rooms_required,
        ]

        if area:
            conditions.append(Hotel.area.ilike(f"%{area}%"))
        if min_rating is not None:
            conditions.append(Hotel.star_rating >= min_rating)
        if max_price_per_night is not None:
            conditions.append(Hotel.price_per_night <= max_price_per_night)

        query = (
            select(Hotel)
            .where(and_(*conditions))
            .order_by(Hotel.star_rating.desc(), Hotel.price_per_night)
            .limit(limit)
        )
        result = await db.execute(query)
        hotels = result.scalars().all()

        # Filter by amenities in Python (JSONB contains check)
        if amenities and hotels:
            required = {a.lower() for a in amenities}
            hotels = [
                h for h in hotels
                if h.amenities and required.issubset({a.lower() for a in h.amenities})
            ]

        if not hotels:
            return {
                "success": True,
                "count": 0,
                "hotels": [],
                "message": (
                    f"No hotels found in {city_norm}. "
                    "The hotel database is currently populated with stub data. "
                    "Real hotels would be fetched from the configured hotel API."
                ),
            }

        return {
            "success": True,
            "count": len(hotels),
            "city": city_norm,
            "hotels": [_hotel_to_dict(h) for h in hotels],
            "message": f"Found {len(hotels)} hotel(s) in {city_norm}.",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Tool: get_hotel_details
# ─────────────────────────────────────────────────────────────────────────────

async def get_hotel_details(hotel_id: str) -> dict:
    """Get full details for a specific hotel by ID."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Hotel).where(Hotel.hotel_id == hotel_id))
        hotel = result.scalar_one_or_none()
        if not hotel:
            return {"success": False, "message": f"Hotel '{hotel_id}' not found.", "hotel": None}
        return {"success": True, "hotel": _hotel_to_dict(hotel)}
