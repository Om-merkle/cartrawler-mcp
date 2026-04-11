"""
CarTrawler MCP Server
======================
Implements the Model Context Protocol (MCP) server exposing all
CarTrawler tools to ChatGPT (developer mode / custom connector).

Transport: Streamable HTTP (SSE-compatible, works with MCP Inspector)
Hosted on: Render.com (public URL)

All tools are individually registered so ChatGPT can select them
intelligently. An additional `agent_query` meta-tool runs the
LangGraph orchestrator for complex multi-step tasks.
"""
from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from cartrawler.config import settings

# ── Tool imports ──────────────────────────────────────────────────────────────
from cartrawler.tools.auth_tools import (
    get_profile,
    login_user,
    logout_user,
    refresh_tokens,
    register_user,
)
from cartrawler.tools.car_tools import (
    book_car,
    get_car_details,
    get_ride_details,
    search_cars,
    search_rides,
)
from cartrawler.tools.faq_tools import answer_faq
from cartrawler.tools.flight_tools import (
    book_flight,
    cancel_booking,
    get_booking_details,
    get_flight_details,
    list_my_bookings,
    search_flights,
)
from cartrawler.tools.hotel_tools import get_hotel_details, search_hotels
from cartrawler.tools.offer_tools import (
    get_all_offers,
    get_applicable_offers,
    validate_coupon,
)

# ── Create MCP app ────────────────────────────────────────────────────────────

mcp = FastMCP(
    name=settings.mcp_server_name,
    instructions=(
        "You are CarTrawler — India's travel booking assistant. "
        "You can search flights, book cars, find hotels, apply coupons, "
        "and answer FAQs. Users must log in before making bookings."
    ),
)


# ═════════════════════════════════════════════════════════════════════════════
# AUTH TOOLS
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def register(
    name: str,
    email: str,
    password: str,
    phone: str = "",
    age: int = 0,
    gender: str = "",
    home_city: str = "",
    preferred_airline: str = "",
    preferred_car_type: str = "",
) -> str:
    """
    Register a new CarTrawler user account.

    Returns JWT access + refresh tokens on success.
    The access_token must be passed to all booking tools.
    """
    result = await register_user(
        name=name,
        email=email,
        password=password,
        phone=phone or None,
        age=age or None,
        gender=gender or None,
        home_city=home_city or None,
        preferred_airline=preferred_airline or None,
        preferred_car_type=preferred_car_type or None,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def login(email: str, password: str) -> str:
    """
    Authenticate with email and password.

    Returns JWT access_token and refresh_token.
    Store the access_token — it is required for all booking operations.
    Token expires in 30 minutes; use refresh_token to renew.
    """
    result = await login_user(email=email, password=password)
    return json.dumps(result, default=str)


@mcp.tool()
async def refresh_session(refresh_token: str) -> str:
    """
    Exchange a refresh token for a new access + refresh token pair.
    Use this when the access token expires (after 30 minutes).
    """
    result = await refresh_tokens(refresh_token=refresh_token)
    return json.dumps(result, default=str)


@mcp.tool()
async def get_my_profile(access_token: str) -> str:
    """
    Fetch the authenticated user's profile: name, email, loyalty tier,
    points, preferences, etc.
    """
    result = await get_profile(access_token=access_token)
    return json.dumps(result, default=str)


@mcp.tool()
async def logout(access_token: str) -> str:
    """Log out the current user by invalidating their refresh token."""
    result = await logout_user(access_token=access_token)
    return json.dumps(result, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# FLIGHT TOOLS
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def find_flights(
    source: str = "",
    destination: str = "",
    source_city: str = "",
    destination_city: str = "",
    cabin_class: str = "Economy",
    max_price: float = 0,
    max_stops: int = -1,
    airline: str = "",
    refundable_only: bool = False,
    limit: int = 20,
) -> str:
    """
    Search available flights between cities or IATA airport codes.

    Examples:
      - DEL → BOM (New Delhi to Mumbai)
      - source_city="Pune" destination_city="Goa"
      - cabin_class="Business" max_stops=0 (direct business class)

    Returns flights sorted by price with airline, duration, price details.
    """
    result = await search_flights(
        source=source or None,
        destination=destination or None,
        source_city=source_city or None,
        destination_city=destination_city or None,
        cabin_class=cabin_class,
        max_price=max_price or None,
        max_stops=max_stops if max_stops >= 0 else None,
        airline=airline or None,
        refundable_only=refundable_only,
        limit=limit,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def flight_details(flight_id: str) -> str:
    """
    Get complete details for a specific flight (e.g. F4001).
    Includes pricing, baggage, meal, wifi, refund policy.
    """
    result = await get_flight_details(flight_id=flight_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def book_a_flight(
    access_token: str,
    flight_id: str,
    travel_date: str,
    cabin_class: str = "Economy",
    payment_method: str = "CARD",
    coupon_code: str = "",
) -> str:
    """
    Book a flight for the authenticated user.

    Requires: access_token from login.
    travel_date format: YYYY-MM-DD
    payment_method: CARD | UPI | WALLET | NET_BANKING
    coupon_code: Optional discount code (e.g. FIRST20, COMBO10)

    Returns booking confirmation with booking_id and loyalty points earned.
    """
    result = await book_flight(
        access_token=access_token,
        flight_id=flight_id,
        travel_date=travel_date,
        cabin_class=cabin_class,
        payment_method=payment_method,
        coupon_code=coupon_code or None,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def my_booking(access_token: str, booking_id: str) -> str:
    """
    Get full details of a specific booking (flight, car, or combo).
    Requires authentication.
    """
    result = await get_booking_details(access_token=access_token, booking_id=booking_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def my_bookings(
    access_token: str,
    status_filter: str = "",
    booking_type: str = "",
    limit: int = 20,
) -> str:
    """
    List all bookings for the authenticated user.

    status_filter: PENDING | CONFIRMED | CANCELLED | COMPLETED
    booking_type: FLIGHT_ONLY | CAR_ONLY | COMBO
    """
    result = await list_my_bookings(
        access_token=access_token,
        status_filter=status_filter or None,
        booking_type=booking_type or None,
        limit=limit,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def cancel_my_booking(access_token: str, booking_id: str) -> str:
    """
    Cancel a booking. Refund eligibility is determined automatically.

    Policy: Refundable flights/cars cancelled ≥2 hrs before departure
    receive a full refund within 5-7 business days.
    """
    result = await cancel_booking(access_token=access_token, booking_id=booking_id)
    return json.dumps(result, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# CAR RENTAL TOOLS
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def find_cars(
    city: str,
    car_type: str = "",
    fuel_type: str = "",
    transmission: str = "",
    with_driver: bool = False,
    max_price_per_day: float = 0,
    vendor: str = "",
    min_rating: float = 0,
    insurance_included: bool = False,
    limit: int = 20,
) -> str:
    """
    Search available rental cars in a city.

    CarTrawler Policy:
    - Minimum driver age: 21 years (Luxury/SUV: 25 years)
    - Refundable security deposit (INR 2,000-10,000) collected at pickup
    - Fuel NOT included in base price
    - Cancellation ≥2 hours before pickup = full refund

    car_type: Sedan | SUV | Hatchback | Luxury | MUV | Compact
    fuel_type: Petrol | Diesel | Electric | CNG
    transmission: Manual | Automatic
    vendor: Zoomcar | Revv | Savaari | Avis | Hertz | CarTrawler | MyChoize | EasyCab
    """
    result = await search_cars(
        city=city,
        car_type=car_type or None,
        fuel_type=fuel_type or None,
        transmission=transmission or None,
        with_driver=with_driver or None,
        max_price_per_day=max_price_per_day or None,
        vendor=vendor or None,
        min_rating=min_rating or None,
        insurance_included=insurance_included or None,
        limit=limit,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def car_details(car_id: str) -> str:
    """
    Get full details for a specific rental car (e.g. C5001).
    Includes vendor, location, pricing, availability, insurance.
    """
    result = await get_car_details(car_id=car_id)
    return json.dumps(result, default=str)


@mcp.tool()
async def book_rental_car(
    access_token: str,
    car_id: str,
    pickup_date: str,
    rental_days: int,
    payment_method: str = "CARD",
    coupon_code: str = "",
) -> str:
    """
    Book a rental car for the authenticated user.

    pickup_date: YYYY-MM-DD
    rental_days: Number of days (minimum 1)
    Note: Security deposit collected at pickup. Fuel not included.
    """
    result = await book_car(
        access_token=access_token,
        car_id=car_id,
        pickup_date=pickup_date,
        rental_days=rental_days,
        payment_method=payment_method,
        coupon_code=coupon_code or None,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def my_rides(
    access_token: str,
    city: str = "",
    travel_date: str = "",
    status_filter: str = "",
) -> str:
    """
    Search all ride/vehicle bookings for the authenticated user.
    Covers airport transfers, hotel pickups, and local city travel.
    """
    result = await search_rides(
        access_token=access_token,
        city=city or None,
        travel_date=travel_date or None,
        status_filter=status_filter or None,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def ride_details(access_token: str, booking_id: str) -> str:
    """
    Get full ride details: vehicle info, pickup location, dates, pricing, status.
    """
    result = await get_ride_details(access_token=access_token, booking_id=booking_id)
    return json.dumps(result, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# HOTEL TOOLS
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def find_hotels(
    city: str,
    area: str = "",
    min_rating: float = 0,
    max_price_per_night: float = 0,
    min_rooms_required: int = 1,
    amenities: str = "",   # comma-separated: "wifi,pool,gym"
) -> str:
    """
    Search hotels at your destination city.

    Useful for building a complete travel itinerary (flight + car + hotel).
    Searches by city, area/locality, star rating, price per night, or amenities.

    amenities: Comma-separated list (e.g. "wifi,pool,restaurant")
    """
    amenity_list = [a.strip() for a in amenities.split(",") if a.strip()] if amenities else None
    result = await search_hotels(
        city=city,
        area=area or None,
        min_rating=min_rating or None,
        max_price_per_night=max_price_per_night or None,
        min_rooms_required=min_rooms_required,
        amenities=amenity_list,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def hotel_details(hotel_id: str) -> str:
    """Get full details for a specific hotel by ID."""
    result = await get_hotel_details(hotel_id=hotel_id)
    return json.dumps(result, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# OFFER / DISCOUNT TOOLS
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_offers(applicable_on: str = "BOTH", city: str = "") -> str:
    """
    List all active discount coupons and offers.

    applicable_on: FLIGHT | CAR | BOTH
    city: Optional city filter for location-specific offers

    Known coupons: FIRST20 (20% first booking), COMBO10 (10% flight+car combo),
    CAR15 (15% car rental), EARLY12 (12% advance booking).
    """
    result = await get_all_offers(
        applicable_on=applicable_on or None,
        city=city or None,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def check_coupon(
    coupon_code: str,
    booking_amount: float,
    applicable_on: str = "BOTH",
    city: str = "",
) -> str:
    """
    Validate a coupon code and calculate the discount for a given amount.

    Returns whether the coupon is valid, the discount amount, and final price.
    """
    result = await validate_coupon(
        coupon_code=coupon_code,
        booking_amount=booking_amount,
        applicable_on=applicable_on,
        city=city or None,
    )
    return json.dumps(result, default=str)


@mcp.tool()
async def best_offers_for_booking(
    booking_amount: float,
    applicable_on: str = "BOTH",
    city: str = "",
    is_first_booking: bool = False,
    loyalty_tier: str = "BRONZE",
) -> str:
    """
    Find the best available discount offers for a booking scenario.
    Automatically calculates savings and ranks offers by discount amount.
    """
    result = await get_applicable_offers(
        booking_amount=booking_amount,
        applicable_on=applicable_on,
        city=city or None,
        is_first_booking=is_first_booking,
        loyalty_tier=loyalty_tier,
    )
    return json.dumps(result, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# FAQ TOOL (No auth required)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def faq(question: str) -> str:
    """
    Answer any question about CarTrawler services using AI-powered search.
    NO LOGIN REQUIRED.

    Topics covered:
    - Flight booking, check-in, baggage policies
    - Car rental policies (age, deposit, fuel, insurance)
    - Refund and cancellation policies
    - Loyalty program (tiers, points, redemption)
    - Available offers and how to use coupons
    - Payment methods (UPI, card, wallet, net banking)
    - Airport information and travel tips
    """
    result = await answer_faq(question=question)
    return json.dumps(result, default=str)


# ═════════════════════════════════════════════════════════════════════════════
# META-TOOL: Agent Query (complex multi-step)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def agent_query(
    query: str,
    access_token: str = "",
    conversation_history_json: str = "",
) -> str:
    """
    Execute a complex multi-step travel request using the AI agent.

    Use this tool for requests like:
    - "Book me a flight from Delhi to Mumbai on July 15 and find a car in Mumbai"
    - "What's the cheapest flight to Goa and what hotels are there?"
    - "Cancel my last booking and show me alternatives"

    The agent automatically decides which sub-tools to invoke.

    access_token: JWT token if user is logged in (optional for FAQs)
    conversation_history_json: JSON array of prior messages for context
    """
    from cartrawler.agent.orchestrator import run_agent

    history = []
    if conversation_history_json:
        try:
            history = json.loads(conversation_history_json)
        except json.JSONDecodeError:
            pass

    result = await run_agent(
        query=query,
        access_token=access_token or None,
        conversation_history=history,
    )
    return json.dumps(result, default=str)


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_mcp_app():
    """Return the FastMCP ASGI app (Starlette-compatible, SSE transport)."""
    return mcp.streamable_http_app()
