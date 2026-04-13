"""
CarTrawler MCP Server
======================
CarTrawler is a CAR RENTAL service. This MCP server exposes car rental
tools to ChatGPT. Flights and hotels are out of scope — we redirect
those queries to other ChatGPT apps and always pitch car rental.

Transport : SSE (ChatGPT Custom Connector compatible)
Hosted on : Render.com
"""
from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from cartrawler.config import settings
from cartrawler.tools.auth_tools import (
    get_profile, login_user, logout_user, refresh_tokens, register_user,
)
from cartrawler.tools.car_tools import (
    book_car, get_car_details, get_ride_details, search_cars, search_rides,
)
from cartrawler.tools.faq_tools import answer_faq
from cartrawler.tools.offer_tools import (
    get_all_offers, get_applicable_offers, validate_coupon,
)

# ── MCP instance ──────────────────────────────────────────────────────────────

mcp = FastMCP(
    name=settings.mcp_server_name,
    instructions="""
You are **CarTrawler** — India's #1 car rental booking assistant.

## Your Scope
- PRIMARY: Car rental search, booking, management, pricing, availability
- You also handle: CarTrawler account (register/login), loyalty points, car rental offers/coupons, cancellation policy, FAQs about car rental

## What You Do NOT Do
- You do NOT book flights or hotels — those are handled by dedicated ChatGPT apps (Kayak, Booking.com etc.)
- You do NOT provide flight discounts or hotel discounts
- You NEVER quote flight prices as part of an offer or deal

## How to Handle Flight / Hotel Queries
When a user asks about flights or hotel bookings:
1. Politely acknowledge and redirect them to ChatGPT's flight/hotel apps
2. ALWAYS follow up by pitching car rental at their destination using the find_cars tool
3. Example: "For flights, please use the Kayak or Google Flights app. But I can help you book a rental car at [destination]! 🚗"

## Authentication Rules
- Account operations (booking, profile, my-bookings, cancel) → ALWAYS ask for login first
- Show the login/register card if user is not authenticated
- FAQ and car search → NO login required

## Display Format
- Always use markdown cards with emojis, tables, and clear headers
- Car search results → show as a formatted table card
- Booking confirmations → show as a confirmation card with all details
- Auth prompts → show as a styled card with clear instructions
""",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


# ── Display card helpers ───────────────────────────────────────────────────────

def _auth_card(action: str = "continue") -> str:
    """Return a formatted authentication-required card."""
    return f"""## 🔐 Login Required

To **{action}**, please authenticate first.

---

### New to CarTrawler?
Use the **`register`** tool:
- `name`, `email`, `password` *(required)*
- `phone`, `age`, `home_city`, `preferred_car_type` *(optional)*

### Already have an account?
Use the **`login`** tool with your `email` and `password`.

> Your session token is valid for **30 minutes**.
> Use `refresh_session` to extend it without re-logging in.
"""


def _flight_redirect_card(destination_city: str = "") -> str:
    """Return a flight-redirect card with car rental pitch."""
    car_pitch = f"\n\n---\n\n### 🚗 Need a Car in {destination_city}?\nI can find you the best rental cars! Just say **\"find cars in {destination_city}\"**." if destination_city else "\n\n---\n\n### 🚗 Need a Rental Car at Your Destination?\nTell me the city and I'll find you the best deals!"
    return f"""## ✈️ Flight Bookings — Not My Department!

CarTrawler specialises in **car rentals**. For flights, please use:

| App | Best For |
|-----|----------|
| 🔍 **Kayak** (ChatGPT plugin) | Compare all airlines |
| 🗺️ **Google Flights** | Price calendar & alerts |
| 🇮🇳 **IndiGo / Air India** apps | Direct airline booking |

{car_pitch}
"""


def _hotel_redirect_card(city: str = "") -> str:
    """Return a hotel-redirect card with car rental pitch."""
    car_pitch = f"\n\n---\n\n### 🚗 Need a Car in {city}?\nI can find rental cars from top vendors like Zoomcar, Avis & Savaari. Just ask!" if city else "\n\n---\n\n### 🚗 Planning to Explore?\nRent a car and go wherever you want — no fixed routes, no schedules!"
    return f"""## 🏨 Hotel Bookings — Not My Department!

CarTrawler specialises in **car rentals**. For hotels, please use:

| App | Best For |
|-----|----------|
| 🏨 **Booking.com** (ChatGPT plugin) | Global hotels |
| 🌟 **MakeMyTrip** | Indian hotels & packages |
| 🛎️ **Oyo / Treebo** apps | Budget stays in India |

{car_pitch}
"""


def _format_cars(result: dict) -> str:
    """Format car search results as a display card."""
    cars = result.get("cars", [])
    if not cars:
        city = result.get("city", "this city")
        return f"## 🚗 No Cars Available\n\nNo rental cars found in **{city}** matching your criteria.\n\nTry adjusting the car type, price range, or date."

    rows = []
    for c in cars[:10]:  # show max 10 in card
        vendor = c.get("vendor", "—")
        model = c.get("car_model", c.get("car_type", "—"))
        price = f"₹{int(c.get('price_per_day', 0)):,}/day"
        rating = f"⭐ {c.get('rating', '—')}"
        location = c.get("pickup_location", c.get("city", "—"))
        car_id = c.get("car_id", "—")
        fuel = c.get("fuel_type", "—")
        avail = "✅" if c.get("availability") else "❌"
        rows.append(f"| {car_id} | {model} | {c.get('car_type','—')} | {fuel} | {price} | {rating} | {avail} | {vendor} | {location} |")

    table = "\n".join(rows)
    total = result.get("total", len(cars))
    city = cars[0].get("city", "") if cars else ""

    display = f"""## 🚗 Rental Cars in {city}

> Showing {len(cars)} of {total} available cars

| Car ID | Model | Type | Fuel | Price | Rating | Available | Vendor | Pickup |
|--------|-------|------|------|-------|--------|-----------|--------|--------|
{table}

---
💡 **To book:** Use the `book_rental_car` tool with the Car ID, pickup date, and number of days.
🏷️ **Offers:** Use `list_offers` to find car rental discounts like `CAR10`, `WEEKEND15`.
"""
    return display


def _format_booking_confirmation(result: dict) -> str:
    """Format a booking confirmation as a display card."""
    if not result.get("success"):
        return f"## ❌ Booking Failed\n\n{result.get('message', 'Unknown error')}"

    b = result.get("booking", {})
    display = f"""## ✅ Booking Confirmed!

---

| Field | Details |
|-------|---------|
| 📋 **Booking ID** | `{b.get('booking_id', '—')}` |
| 🚗 **Car** | {b.get('car_model', '—')} ({b.get('car_type', '—')}) |
| 📍 **Pickup** | {b.get('pickup_location', '—')} |
| 📅 **Pickup Date** | {b.get('pickup_date', '—')} |
| 🔄 **Return Date** | {b.get('return_date', '—')} |
| ⏱️ **Duration** | {b.get('rental_days', '—')} day(s) |
| 💰 **Total Paid** | ₹{int(b.get('total_price', 0)):,} |
| 🏷️ **Discount** | ₹{int(b.get('discount_applied', 0)):,} |
| 💳 **Payment** | {b.get('payment_method', '—')} |
| ⭐ **Loyalty Points** | +{b.get('loyalty_points_earned', 0)} points |

---
> 🔑 Save your Booking ID for cancellations or enquiries.
> ⛽ Fuel not included. Security deposit collected at pickup.
"""
    return display


def _format_profile(result: dict) -> str:
    """Format user profile as a display card."""
    if not result.get("success"):
        return f"## ❌ {result.get('message', 'Error')}"

    p = result.get("profile", {})
    tier_emoji = {"BRONZE": "🥉", "SILVER": "🥈", "GOLD": "🥇", "PLATINUM": "💎"}.get(p.get("loyalty_tier", ""), "🎖️")
    display = f"""## 👤 My CarTrawler Profile

---

| | |
|--|--|
| **Name** | {p.get('name', '—')} |
| **Email** | {p.get('email', '—')} |
| **Phone** | {p.get('phone', '—')} |
| **Home City** | {p.get('home_city', '—')} |
| **Preferred Car** | {p.get('preferred_car_type', '—')} |

### {tier_emoji} Loyalty Status
| Tier | Points |
|------|--------|
| **{p.get('loyalty_tier', 'BRONZE')}** | {p.get('loyalty_points', 0):,} pts |

---
> 🥉 Bronze: 0–999 pts &nbsp; 🥈 Silver: 1,000–2,499 pts &nbsp; 🥇 Gold: 2,500–4,999 pts &nbsp; 💎 Platinum: 5,000+ pts
"""
    return display


def _format_offers(result: dict) -> str:
    """Format car rental offers as a display card."""
    offers = result.get("offers", [])
    if not offers:
        return "## 🏷️ No Active Offers\n\nCheck back soon for new car rental deals!"

    rows = []
    for o in offers:
        code = f"`{o.get('coupon_code', '—')}`"
        desc = o.get("description", "—")[:50]
        disc = f"{int(o.get('discount_percentage', 0))}% off" if o.get("discount_percentage") else f"₹{int(o.get('max_discount_amount', 0))} off"
        min_amt = f"₹{int(o.get('min_booking_amount', 0)):,}" if o.get("min_booking_amount") else "—"
        valid = o.get("valid_till", "—")
        rows.append(f"| {code} | {desc} | {disc} | {min_amt} | {valid} |")

    table = "\n".join(rows)
    display = f"""## 🏷️ Car Rental Offers & Coupons

| Code | Description | Discount | Min. Booking | Valid Till |
|------|-------------|----------|--------------|------------|
{table}

---
💡 Apply any coupon code when using `book_rental_car`.
"""
    return display


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
    preferred_car_type: str = "",
) -> str:
    """
    Create a new CarTrawler account.

    Returns JWT access_token + refresh_token. Save the access_token —
    it is required for all booking and account operations.
    """
    result = await register_user(
        name=name, email=email, password=password,
        phone=phone or None, age=age or None, gender=gender or None,
        home_city=home_city or None, preferred_car_type=preferred_car_type or None,
    )
    if result.get("success"):
        tokens = result.get("tokens", {})
        return f"""## 🎉 Welcome to CarTrawler, {name}!

Your account has been created successfully.

---

| | |
|--|--|
| **User ID** | `{result.get('user_id', '—')}` |
| **Loyalty Tier** | 🥉 Bronze |
| **Points** | 0 pts |

### 🔑 Your Access Token
```
{tokens.get('access_token', '—')}
```

### 🔄 Your Refresh Token
```
{tokens.get('refresh_token', '—')}
```

> ⚠️ Token expires in **30 minutes**. Use `refresh_session` to renew.

---
🚗 **Ready to book your first car?** Try `find_cars` with your city!
"""
    return f"## ❌ Registration Failed\n\n{result.get('message', 'Unknown error')}"


@mcp.tool()
async def login(email: str, password: str) -> str:
    """
    Login to CarTrawler with email and password.

    Returns JWT access_token (valid 30 min) and refresh_token.
    The access_token is required for booking, cancellation, and profile operations.
    """
    result = await login_user(email=email, password=password)
    if result.get("success"):
        tokens = result.get("tokens", {})
        tier = tokens.get("loyalty_tier", "BRONZE")
        tier_emoji = {"BRONZE": "🥉", "SILVER": "🥈", "GOLD": "🥇", "PLATINUM": "💎"}.get(tier, "🎖️")
        return f"""## ✅ Login Successful

Welcome back, **{tokens.get('name', 'User')}**! 👋

---

| | |
|--|--|
| **Loyalty Tier** | {tier_emoji} {tier} |
| **Points** | {tokens.get('loyalty_points', 0):,} pts |

### 🔑 Your Access Token
```
{tokens.get('access_token', '—')}
```

### 🔄 Your Refresh Token
```
{tokens.get('refresh_token', '—')}
```

> ⚠️ Token expires in **30 minutes**. Use `refresh_session` to renew.

---
🚗 What would you like to do?
- `find_cars` — Search rental cars
- `my_bookings` — View your bookings
- `my_profile` — View your profile
"""
    return f"## ❌ Login Failed\n\n{result.get('message', 'Incorrect email or password.')}"


@mcp.tool()
async def refresh_session(refresh_token: str) -> str:
    """
    Renew your session without logging in again.
    Exchange your refresh_token for a new access_token + refresh_token pair.
    Use this when the access_token expires (after 30 minutes).
    """
    result = await refresh_tokens(refresh_token=refresh_token)
    if result.get("success"):
        tokens = result.get("tokens", {})
        return f"""## 🔄 Session Renewed

### 🔑 New Access Token
```
{tokens.get('access_token', '—')}
```

> Valid for another **30 minutes**.
"""
    return f"## ❌ Session Expired\n\n{result.get('message', '')}\n\nPlease use the `login` tool to sign in again."


@mcp.tool()
async def my_profile(access_token: str) -> str:
    """
    View your CarTrawler profile: name, email, loyalty tier, points, preferences.
    Requires login — get your access_token using the `login` tool.
    """
    result = await get_profile(access_token=access_token)
    return _format_profile(result)


@mcp.tool()
async def logout(access_token: str) -> str:
    """Log out and invalidate your current session token."""
    await logout_user(access_token=access_token)
    return "## 👋 Logged Out\n\nYou have been logged out of CarTrawler.\n\nUse `login` to sign in again."


# ═════════════════════════════════════════════════════════════════════════════
# FLIGHT REDIRECT (not our service — redirect + pitch cars)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def find_flights(
    source_city: str = "",
    destination_city: str = "",
    travel_date: str = "",
) -> str:
    """
    CarTrawler does not book flights. This tool redirects users to flight
    apps and pitches car rental at the destination.

    Call this when user asks about flights, so they get redirected AND
    a car rental suggestion for their destination.
    """
    card = _flight_redirect_card(destination_city)
    if destination_city:
        try:
            cars_result = await search_cars(city=destination_city, limit=3)
            top_cars = cars_result.get("cars", [])
            if top_cars:
                car_lines = "\n".join(
                    f"- **{c.get('car_model','Car')}** ({c.get('car_type','')}) — ₹{int(c.get('price_per_day',0)):,}/day @ {c.get('vendor','')}"
                    for c in top_cars
                )
                card += f"\n### 🔥 Top Cars in {destination_city}\n{car_lines}\n\n> 👉 Use `find_cars` with city=**\"{destination_city}\"** to see all options."
        except Exception:
            pass
    return card


@mcp.tool()
async def book_flight(
    source_city: str = "",
    destination_city: str = "",
    travel_date: str = "",
) -> str:
    """
    CarTrawler does not book flights. Redirects to flight apps and offers car rental.
    """
    return _flight_redirect_card(destination_city)


# ═════════════════════════════════════════════════════════════════════════════
# HOTEL REDIRECT (not our service — redirect + pitch cars)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def find_hotels(
    city: str = "",
    check_in: str = "",
    check_out: str = "",
) -> str:
    """
    CarTrawler does not book hotels. This tool redirects users to hotel
    apps and pitches car rental at the destination.

    Call this when user asks about hotels, so they get redirected AND
    a car rental suggestion for their stay.
    """
    card = _hotel_redirect_card(city)
    if city:
        try:
            cars_result = await search_cars(city=city, limit=3)
            top_cars = cars_result.get("cars", [])
            if top_cars:
                car_lines = "\n".join(
                    f"- **{c.get('car_model','Car')}** ({c.get('car_type','')}) — ₹{int(c.get('price_per_day',0)):,}/day @ {c.get('vendor','')}"
                    for c in top_cars
                )
                card += f"\n### 🔥 Available Cars in {city}\n{car_lines}\n\n> 👉 Use `find_cars` with city=**\"{city}\"** to book."
        except Exception:
            pass
    return card


@mcp.tool()
async def book_hotel(
    city: str = "",
    check_in: str = "",
    check_out: str = "",
) -> str:
    """
    CarTrawler does not book hotels. Redirects to hotel apps and offers car rental.
    """
    return _hotel_redirect_card(city)


# ═════════════════════════════════════════════════════════════════════════════
# CAR RENTAL TOOLS  ← Core service
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
    Search available rental cars in any Indian city. ← CORE SERVICE

    car_type: Sedan | SUV | Hatchback | Luxury | MUV | Compact
    fuel_type: Petrol | Diesel | CNG
    transmission: Manual | Automatic
    vendor: Zoomcar | Revv | Savaari | Avis | MyChoize | EasyCab | CarTrawler

    Policy:
    - Minimum age: 21 yrs (Luxury/SUV: 25 yrs)
    - Security deposit: ₹2,000–10,000 at pickup (fully refundable)
    - Fuel not included in base price
    - Free cancellation ≥ 2 hours before pickup
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
    return _format_cars(result)


@mcp.tool()
async def car_details(car_id: str) -> str:
    """
    Get complete details for a rental car by its ID (e.g. C5001).
    Shows vendor, pickup location, pricing, availability, insurance, fuel type.
    """
    result = await get_car_details(car_id=car_id)
    if not result.get("success"):
        return f"## ❌ Car Not Found\n\n`{car_id}` was not found."

    c = result.get("car", {})
    ins = "✅ Included" if c.get("insurance_included") else "❌ Not Included"
    ac = "✅" if c.get("ac") else "❌"
    driver = "✅ Available" if c.get("with_driver") else "❌ Self-drive only"
    avail = "✅ Available" if c.get("availability") else "❌ Not Available"

    display = f"""## 🚗 {c.get('car_model', 'Car Details')}

---

| | |
|--|--|
| **Car ID** | `{c.get('car_id', '—')}` |
| **Type** | {c.get('car_type', '—')} |
| **Fuel** | {c.get('fuel_type', '—')} |
| **Transmission** | {c.get('transmission', '—')} |
| **Seats** | {c.get('seating_capacity', '—')} |
| **AC** | {ac} |
| **Insurance** | {ins} |
| **With Driver** | {driver} |
| **Availability** | {avail} |
| **Rating** | ⭐ {c.get('rating', '—')} ({c.get('total_reviews', 0)} reviews) |

### 💰 Pricing
| Duration | Price |
|----------|-------|
| Per Day | ₹{int(c.get('price_per_day', 0)):,} |
| Per Hour | ₹{int(c.get('price_per_hour', 0)):,} |
| Min. Age | {c.get('min_age_required', 21)} years |

### 📍 Pickup Location
**{c.get('vendor', '—')}** — {c.get('pickup_location', '—')}, {c.get('city', '—')}

---
> 👉 Ready to book? Use `book_rental_car` with Car ID `{c.get('car_id', car_id)}`
"""
    return display


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
    Book a rental car. LOGIN REQUIRED — get access_token via `login`.

    pickup_date: YYYY-MM-DD
    rental_days: Minimum 1 day
    payment_method: CARD | UPI | WALLET | NET_BANKING
    coupon_code: Optional (try CAR10, WEEKEND15, COMBO10)

    Note: Fuel not included. Security deposit collected at pickup.
    Free cancellation if cancelled ≥ 2 hours before pickup.
    """
    if not access_token:
        return _auth_card("book a rental car")

    result = await book_car(
        access_token=access_token,
        car_id=car_id,
        pickup_date=pickup_date,
        rental_days=rental_days,
        payment_method=payment_method,
        coupon_code=coupon_code or None,
    )
    return _format_booking_confirmation(result)


@mcp.tool()
async def my_bookings(
    access_token: str,
    status_filter: str = "",
    limit: int = 20,
) -> str:
    """
    View all your car rental bookings. LOGIN REQUIRED.

    status_filter: PENDING | CONFIRMED | CANCELLED | COMPLETED
    """
    if not access_token:
        return _auth_card("view your bookings")

    from cartrawler.tools.flight_tools import list_my_bookings
    result = await list_my_bookings(
        access_token=access_token,
        status_filter=status_filter or None,
        booking_type="CAR_ONLY",
        limit=limit,
    )
    bookings = result.get("bookings", [])
    if not bookings:
        display = "## 📋 My Bookings\n\nNo car rental bookings found."
    else:
        rows = []
        for b in bookings:
            bid = b.get("booking_id", "—")
            car = b.get("car_id", "—")
            date = b.get("travel_date", "—")
            days = b.get("rental_days", "—")
            total = f"₹{int(b.get('total_price', 0)):,}"
            status = b.get("status", "—")
            rows.append(f"| `{bid}` | {car} | {date} | {days}d | {total} | {status} |")
        table = "\n".join(rows)
        display = f"""## 📋 My Car Rental Bookings

| Booking ID | Car | Date | Days | Total | Status |
|-----------|-----|------|------|-------|--------|
{table}

> Use `cancel_booking` with a Booking ID to cancel a booking.
"""
    return display


@mcp.tool()
async def cancel_booking(access_token: str, booking_id: str) -> str:
    """
    Cancel a car rental booking. LOGIN REQUIRED.

    Policy: Free cancellation if cancelled ≥ 2 hours before pickup.
    Refund processed in 3–5 business days to original payment method.
    """
    if not access_token:
        return _auth_card("cancel a booking")

    from cartrawler.tools.flight_tools import cancel_booking as _cancel
    result = await _cancel(access_token=access_token, booking_id=booking_id)
    if result.get("success"):
        display = f"""## ✅ Booking Cancelled

| | |
|--|--|
| **Booking ID** | `{booking_id}` |
| **Refund** | {result.get('refund_amount', 'Per policy')} |
| **Timeline** | 3–5 business days |
| **Payment Method** | Original payment method |

> Your refund will be processed within 3–5 business days.
"""
    else:
        display = f"## ❌ Cancellation Failed\n\n{result.get('message', 'Could not cancel booking.')}"
    return display


@mcp.tool()
async def my_rides(
    access_token: str,
    city: str = "",
    travel_date: str = "",
    status_filter: str = "",
) -> str:
    """
    View airport transfers and city ride bookings. LOGIN REQUIRED.
    """
    if not access_token:
        return _auth_card("view your rides")

    result = await search_rides(
        access_token=access_token,
        city=city or None,
        travel_date=travel_date or None,
        status_filter=status_filter or None,
    )
    rides = result.get("rides", [])
    if not rides:
        return "## 🚕 My Rides\n\nNo rides found."
    rows = [f"| `{r.get('booking_id','—')}` | {r.get('car_id','—')} | {r.get('travel_date','—')} | {r.get('status','—')} |" for r in rides]
    return f"## 🚕 My Rides\n\n| Booking ID | Car | Date | Status |\n|-----------|-----|------|--------|\n" + "\n".join(rows)


# ═════════════════════════════════════════════════════════════════════════════
# CAR RENTAL OFFERS (only — no flight/hotel discounts)
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def car_offers(city: str = "") -> str:
    """
    List all active car rental discounts and coupon codes.

    CarTrawler ONLY provides discounts on car rentals.
    For flight or hotel discounts, please check those respective apps.

    Returns coupon codes, discount %, and eligibility criteria.
    """
    result = await get_all_offers(applicable_on="CAR", city=city or None)
    return _format_offers(result)


@mcp.tool()
async def best_car_offer(
    booking_amount: float,
    city: str = "",
    is_first_booking: bool = False,
    loyalty_tier: str = "BRONZE",
) -> str:
    """
    Find the best car rental coupon for a given booking amount.
    Returns ranked list of applicable offers with calculated savings.

    loyalty_tier: BRONZE | SILVER | GOLD | PLATINUM
    """
    result = await get_applicable_offers(
        booking_amount=booking_amount,
        applicable_on="CAR",
        city=city or None,
        is_first_booking=is_first_booking,
        loyalty_tier=loyalty_tier,
    )
    return _format_offers(result)


@mcp.tool()
async def validate_car_coupon(
    coupon_code: str,
    booking_amount: float,
    city: str = "",
) -> str:
    """
    Validate a car rental coupon code and calculate the discount.
    Returns the discount amount and final price after applying the coupon.
    """
    result = await validate_coupon(
        coupon_code=coupon_code,
        booking_amount=booking_amount,
        applicable_on="CAR",
        city=city or None,
    )
    if result.get("valid"):
        display = f"""## ✅ Coupon Valid: `{coupon_code}`

| | |
|--|--|
| **Original Price** | ₹{int(booking_amount):,} |
| **Discount** | ₹{int(result.get('discount_amount', 0)):,} |
| **Final Price** | ₹{int(result.get('final_price', booking_amount)):,} |
| **You Save** | {result.get('discount_percentage', 0)}% |
"""
    else:
        display = f"## ❌ Coupon Invalid\n\n`{coupon_code}` — {result.get('message', 'Not applicable.')}\n\nTry `car_offers` to see valid codes."
    return display


# ═════════════════════════════════════════════════════════════════════════════
# FAQ — Car rental knowledge base
# ═════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def faq(question: str) -> str:
    """
    Answer any question about CarTrawler car rental services.
    No login required.

    Topics: rental policies, age requirements, cancellation, refunds,
    fuel, insurance, loyalty points, coupon usage, pickup/drop process.
    """
    result = await answer_faq(question=question)
    answer = result.get("answer", "")
    sources = result.get("sources", [])

    if result.get("success") and sources:
        return f"""## 💬 CarTrawler FAQ

**Q: {question}**

---

{answer}

---
*Based on {len(sources)} knowledge base source(s)*
"""
    return f"""## 💬 CarTrawler FAQ

**Q: {question}**

---

{answer}

---
> 📞 For further help: Contact CarTrawler support
"""


# ─────────────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────────────

def create_mcp_app():
    """Return the FastMCP ASGI app using SSE transport (ChatGPT-compatible)."""
    return mcp.sse_app()
