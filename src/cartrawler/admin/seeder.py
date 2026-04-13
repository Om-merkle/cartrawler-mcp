"""
CarTrawler DB Seeder — importable module
=========================================
Uses the app's own engine (same DATABASE_URL, same SSL config) so it
works identically on Render as the rest of the app.

Called from the /admin/seed endpoint in main.py.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from cartrawler.db.database import engine
from cartrawler.db.models import (
    Base,
    Booking,
    Car,
    Flight,
    Hotel,
    KnowledgeBase,
    Offer,
    SearchLog,
    User,
    UserSession,
)

logger = logging.getLogger("cartrawler.admin.seeder")

# data/ is at the repo root.
# __file__ = {repo_root}/src/cartrawler/admin/seeder.py
# parents[3] = {repo_root}
DATA_DIR = Path(__file__).resolve().parents[3] / "data"


# ── helpers ───────────────────────────────────────────────────────────────────

def _bool(val: str) -> bool:
    return str(val).strip().lower() in ("true", "1", "yes")


def _int_or_none(val: str) -> int | None:
    v = str(val).strip()
    return int(v) if v else None


def _float_or_none(val: str) -> float | None:
    v = str(val).strip()
    return float(v) if v else None


def _date_or_none(val: str) -> date | None:
    v = str(val).strip()
    return date.fromisoformat(v[:10]) if v else None


def _json_or_none(val: str) -> Any:
    v = str(val).strip()
    if not v:
        return None
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return None


def _read_csv(filename: str) -> list[dict[str, str]]:
    path = DATA_DIR / filename
    if not path.exists():
        logger.warning("CSV not found: %s", path)
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ── seeders ───────────────────────────────────────────────────────────────────

async def _seed_users(session: AsyncSession) -> int:
    rows = _read_csv("users.csv")
    session.add_all([User(
        user_id=r["user_id"], name=r["name"], email=r["email"],
        phone=r.get("phone") or None,
        age=_int_or_none(r.get("age", "")),
        gender=r.get("gender") or None,
        nationality=r.get("nationality") or None,
        preferred_car_type=r.get("preferred_car_type") or None,
        preferred_airline=r.get("preferred_airline") or None,
        home_city=r.get("home_city") or None,
        loyalty_tier=r.get("loyalty_tier", "BRONZE"),
        loyalty_points=_int_or_none(r.get("loyalty_points", "0")) or 0,
        hashed_password=None, is_active=True, is_verified=True,
    ) for r in rows])
    return len(rows)


async def _seed_flights(session: AsyncSession) -> int:
    rows = _read_csv("flights.csv")
    session.add_all([Flight(
        flight_id=r["flight_id"], airline=r["airline"],
        flight_number=r["flight_number"],
        source=r["source"], destination=r["destination"],
        source_city=r.get("source_city") or None,
        destination_city=r.get("destination_city") or None,
        departure_time=r.get("departure_time") or None,
        arrival_time=r.get("arrival_time") or None,
        duration_mins=_int_or_none(r.get("duration_mins", "")),
        price_economy=_float_or_none(r.get("price_economy", "")),
        price_business=_float_or_none(r.get("price_business", "")),
        stops=_int_or_none(r.get("stops", "0")) or 0,
        aircraft=r.get("aircraft") or None,
        available_seats=_int_or_none(r.get("available_seats", "")),
        baggage_kg=_int_or_none(r.get("baggage_kg", "")),
        refundable=_bool(r.get("refundable", "false")),
        meal_included=_bool(r.get("meal_included", "false")),
        wifi_available=_bool(r.get("wifi_available", "false")),
    ) for r in rows])
    return len(rows)


async def _seed_cars(session: AsyncSession) -> int:
    rows = _read_csv("cars.csv")
    session.add_all([Car(
        car_id=r["car_id"], vendor=r.get("vendor") or None,
        city=r["city"], pickup_location=r.get("pickup_location") or None,
        car_type=r.get("car_type") or None,
        car_model=r.get("car_model") or None,
        fuel_type=r.get("fuel_type") or None,
        transmission=r.get("transmission") or None,
        seating_capacity=_int_or_none(r.get("seating_capacity", "")),
        price_per_day=_float_or_none(r.get("price_per_day", "")),
        price_per_hour=_float_or_none(r.get("price_per_hour", "")),
        with_driver=_bool(r.get("with_driver", "false")),
        availability=_bool(r.get("availability", "true")),
        rating=_float_or_none(r.get("rating", "")),
        total_reviews=_int_or_none(r.get("total_reviews", "")),
        ac=_bool(r.get("ac", "true")),
        insurance_included=_bool(r.get("insurance_included", "false")),
        min_age_required=_int_or_none(r.get("min_age_required", "21")) or 21,
    ) for r in rows])
    return len(rows)


async def _seed_offers(session: AsyncSession) -> int:
    rows = _read_csv("offers.csv")
    session.add_all([Offer(
        offer_id=r["offer_id"],
        trigger_event=r.get("trigger_event") or None,
        coupon_code=r["coupon_code"],
        description=r.get("description") or None,
        discount_percentage=_float_or_none(r.get("discount_percentage", "")),
        max_discount_amount=_float_or_none(r.get("max_discount_amount", "")),
        min_booking_amount=_float_or_none(r.get("min_booking_amount", "")),
        valid_city=r.get("valid_city", "ALL"),
        applicable_on=r.get("applicable_on", "BOTH"),
        valid_from=_date_or_none(r.get("valid_from", "")),
        valid_till=_date_or_none(r.get("valid_till", "")),
        is_active=_bool(r.get("is_active", "true")),
    ) for r in rows])
    return len(rows)


async def _seed_bookings(session: AsyncSession) -> int:
    rows = _read_csv("bookings.csv")
    session.add_all([Booking(
        booking_id=r["booking_id"], user_id=r["user_id"],
        booking_type=r["booking_type"],
        flight_id=r.get("flight_id") or None,
        flight_price=_float_or_none(r.get("flight_price", "")),
        car_id=r.get("car_id") or None,
        rental_days=_int_or_none(r.get("rental_days", "")),
        car_price=_float_or_none(r.get("car_price", "")),
        travel_date=_date_or_none(r["travel_date"]),
        return_date=_date_or_none(r.get("return_date", "")),
        discount_applied=_float_or_none(r.get("discount_applied", "0")) or 0,
        total_price=float(r["total_price"]),
        status=r.get("status", "PENDING"),
        payment_status=r.get("payment_status", "PENDING"),
        payment_method=r.get("payment_method") or None,
        coupon_code=r.get("coupon_code") or None,
        booking_date=_date_or_none(r.get("booking_date", "")),
        cancellation_date=_date_or_none(r.get("cancellation_date", "")),
    ) for r in rows])
    return len(rows)


async def _seed_search_logs(session: AsyncSession) -> int:
    rows = _read_csv("search_logs.csv")
    session.add_all([SearchLog(
        search_id=r["search_id"], user_id=r["user_id"],
        source=r.get("source") or None,
        destination=r.get("destination") or None,
        source_city=r.get("source_city") or None,
        destination_city=r.get("destination_city") or None,
        travel_date=_date_or_none(r.get("travel_date", "")),
        return_date=_date_or_none(r.get("return_date", "")),
        passengers=_int_or_none(r.get("passengers", "1")) or 1,
        cabin_class=r.get("cabin_class", "Economy"),
        include_car=_bool(r.get("include_car", "false")),
        car_type_preference=r.get("car_type_preference") or None,
        budget_max=_float_or_none(r.get("budget_max", "")),
        search_result_count=_int_or_none(r.get("search_result_count", "0")) or 0,
    ) for r in rows])
    return len(rows)


async def _seed_sessions(session: AsyncSession) -> int:
    rows = _read_csv("sessions.csv")
    session.add_all([UserSession(
        session_id=r["session_id"], user_id=r["user_id"],
        channel=r.get("channel") or None,
        intent=r.get("intent") or None,
        context=_json_or_none(r.get("context", "")),
        resolved=_bool(r.get("resolved", "false")),
        session_duration_secs=_int_or_none(r.get("session_duration_secs", "")),
    ) for r in rows])
    return len(rows)


async def _seed_knowledge_base(session: AsyncSession) -> int:
    rows = _read_csv("knowledge_base.csv")
    session.add_all([KnowledgeBase(
        kb_id=r["kb_id"], topic=r["topic"], content=r["content"],
        embedding_ready=_bool(r.get("embedding_ready", "false")),
        chunk_type=r.get("chunk_type") or None,
        language=r.get("language", "en"),
        last_updated=_date_or_none(r.get("last_updated", "")),
    ) for r in rows])
    return len(rows)


async def _seed_hotels(session: AsyncSession) -> int:
    rows = _read_csv("hotels.csv")
    session.add_all([Hotel(
        hotel_id=r["hotel_id"], name=r["name"], city=r["city"],
        area=r.get("area") or None,
        address=r.get("address") or None,
        star_rating=_float_or_none(r.get("star_rating", "")),
        price_per_night=_float_or_none(r.get("price_per_night", "")),
        amenities=_json_or_none(r.get("amenities", "")),
        total_rooms=_int_or_none(r.get("total_rooms", "")),
        available_rooms=_int_or_none(r.get("available_rooms", "")),
        check_in_time=r.get("check_in_time") or None,
        check_out_time=r.get("check_out_time") or None,
        image_url=r.get("image_url") or None,
        is_active=_bool(r.get("is_active", "true")),
    ) for r in rows])
    return len(rows)


# ── ordered seeders ───────────────────────────────────────────────────────────

_SEEDERS = [
    ("users",          _seed_users),
    ("flights",        _seed_flights),
    ("cars",           _seed_cars),
    ("offers",         _seed_offers),
    ("bookings",       _seed_bookings),
    ("search_logs",    _seed_search_logs),
    ("sessions",       _seed_sessions),
    ("knowledge_base", _seed_knowledge_base),
    ("hotels",         _seed_hotels),
]


# ── public entry point ────────────────────────────────────────────────────────

async def run_seed() -> dict[str, int]:
    """
    Drop all tables, recreate them, and seed from data/*.csv.
    Uses the app's shared engine so it works on Render without any
    extra config.  Returns a dict of {table: rows_inserted}.
    """
    logger.info("Seed started. DATA_DIR=%s", DATA_DIR)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("Dropping all tables…")
        await conn.run_sync(Base.metadata.drop_all)
        logger.info("Recreating tables…")
        await conn.run_sync(Base.metadata.create_all)

    results: dict[str, object] = {}
    async with AsyncSession(engine) as session:
        for table_name, seeder in _SEEDERS:
            try:
                count = await seeder(session)
                await session.commit()
                results[table_name] = count
                logger.info("  seeded %-20s %d rows", table_name, count)
            except Exception as exc:
                await session.rollback()
                error_msg = str(exc)
                logger.error("  FAILED %-20s %s", table_name, error_msg)
                results[table_name] = {"error": error_msg}

    logger.info("Seed complete: %s", results)
    return results
