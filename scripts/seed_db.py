"""
CarTrawler Database Seeder
==========================
Loads CSV data files into PostgreSQL (Supabase) and creates
all tables if they don't already exist.

Usage:
    uv run python scripts/seed_db.py           # seed all tables
    uv run python scripts/seed_db.py --table users   # seed one table
    uv run python scripts/seed_db.py --drop    # drop + recreate + seed

Reads CSVs from: <repo_root>/data/
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# ── Path setup (run from repo root or scripts/) ────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from cartrawler.config import settings
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed")

DATA_DIR = REPO_ROOT / "data"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bool(val: str) -> bool:
    return str(val).strip().lower() in ("true", "1", "yes")


def _int_or_none(val: str) -> int | None:
    v = val.strip()
    return int(v) if v else None


def _float_or_none(val: str) -> float | None:
    v = val.strip()
    return float(v) if v else None


def _date_or_none(val: str) -> date | None:
    v = val.strip()
    if not v:
        return None
    return date.fromisoformat(v[:10])  # handles datetime strings too


def _json_or_none(val: str) -> Any:
    v = val.strip()
    if not v:
        return None
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return None


def read_csv(filename: str) -> list[dict[str, str]]:
    path = DATA_DIR / filename
    if not path.exists():
        logger.warning("CSV not found: %s — skipping", path)
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ─────────────────────────────────────────────────────────────────────────────
# Table seeders
# ─────────────────────────────────────────────────────────────────────────────

async def seed_users(session: AsyncSession) -> int:
    rows = read_csv("users.csv")
    objects = []
    for r in rows:
        objects.append(User(
            user_id=r["user_id"],
            name=r["name"],
            email=r["email"],
            phone=r.get("phone") or None,
            age=_int_or_none(r.get("age", "")),
            gender=r.get("gender") or None,
            nationality=r.get("nationality") or None,
            preferred_car_type=r.get("preferred_car_type") or None,
            preferred_airline=r.get("preferred_airline") or None,
            home_city=r.get("home_city") or None,
            loyalty_tier=r.get("loyalty_tier", "BRONZE"),
            loyalty_points=_int_or_none(r.get("loyalty_points", "0")) or 0,
            hashed_password=None,  # seed users have no password
            is_active=True,
            is_verified=True,
        ))
    session.add_all(objects)
    return len(objects)


async def seed_flights(session: AsyncSession) -> int:
    rows = read_csv("flights.csv")
    objects = []
    for r in rows:
        objects.append(Flight(
            flight_id=r["flight_id"],
            airline=r["airline"],
            flight_number=r["flight_number"],
            source=r["source"],
            destination=r["destination"],
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
        ))
    session.add_all(objects)
    return len(objects)


async def seed_cars(session: AsyncSession) -> int:
    rows = read_csv("cars.csv")
    objects = []
    for r in rows:
        objects.append(Car(
            car_id=r["car_id"],
            vendor=r.get("vendor") or None,
            city=r["city"],
            pickup_location=r.get("pickup_location") or None,
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
        ))
    session.add_all(objects)
    return len(objects)


async def seed_bookings(session: AsyncSession) -> int:
    rows = read_csv("bookings.csv")
    objects = []
    for r in rows:
        objects.append(Booking(
            booking_id=r["booking_id"],
            user_id=r["user_id"],
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
        ))
    session.add_all(objects)
    return len(objects)


async def seed_offers(session: AsyncSession) -> int:
    rows = read_csv("offers.csv")
    objects = []
    for r in rows:
        objects.append(Offer(
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
        ))
    session.add_all(objects)
    return len(objects)


async def seed_search_logs(session: AsyncSession) -> int:
    rows = read_csv("search_logs.csv")
    objects = []
    for r in rows:
        objects.append(SearchLog(
            search_id=r["search_id"],
            user_id=r["user_id"],
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
        ))
    session.add_all(objects)
    return len(objects)


async def seed_sessions(session: AsyncSession) -> int:
    rows = read_csv("sessions.csv")
    objects = []
    for r in rows:
        objects.append(UserSession(
            session_id=r["session_id"],
            user_id=r["user_id"],
            channel=r.get("channel") or None,
            intent=r.get("intent") or None,
            context=_json_or_none(r.get("context", "")),
            resolved=_bool(r.get("resolved", "false")),
            session_duration_secs=_int_or_none(r.get("session_duration_secs", "")),
        ))
    session.add_all(objects)
    return len(objects)


async def seed_knowledge_base(session: AsyncSession) -> int:
    rows = read_csv("knowledge_base.csv")
    objects = []
    for r in rows:
        objects.append(KnowledgeBase(
            kb_id=r["kb_id"],
            topic=r["topic"],
            content=r["content"],
            embedding_ready=_bool(r.get("embedding_ready", "false")),
            chunk_type=r.get("chunk_type") or None,
            language=r.get("language", "en"),
            last_updated=_date_or_none(r.get("last_updated", "")),
        ))
    session.add_all(objects)
    return len(objects)


async def seed_hotels(session: AsyncSession) -> int:
    rows = read_csv("hotels.csv")
    objects = []
    for r in rows:
        objects.append(Hotel(
            hotel_id=r["hotel_id"],
            name=r["name"],
            city=r["city"],
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
        ))
    session.add_all(objects)
    return len(objects)


# ─────────────────────────────────────────────────────────────────────────────
# Enable pgvector extension
# ─────────────────────────────────────────────────────────────────────────────

async def enable_pgvector(session: AsyncSession) -> None:
    try:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.commit()
        logger.info("pgvector extension enabled")
    except Exception as exc:
        logger.warning("Could not enable pgvector: %s", exc)
        await session.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

SEEDERS: dict[str, Any] = {
    "users": seed_users,
    "flights": seed_flights,
    "cars": seed_cars,
    "bookings": seed_bookings,
    "offers": seed_offers,
    "search_logs": seed_search_logs,
    "sessions": seed_sessions,
    "knowledge_base": seed_knowledge_base,
    "hotels": seed_hotels,
}

# Seeding order respects FK dependencies
SEED_ORDER = [
    "users",
    "flights",
    "cars",
    "offers",
    "bookings",   # depends on users, flights, cars
    "search_logs",
    "sessions",
    "knowledge_base",
    "hotels",
]


async def _run(tables: list[str], drop: bool = False) -> None:
    engine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        echo=False,
    )

    async with engine.begin() as conn:
        # Enable pgvector before creating tables
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension ready")

        if drop:
            logger.warning("Dropping all tables...")
            await conn.run_sync(Base.metadata.drop_all)

        logger.info("Creating tables (if not exist)...")
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        for table_name in tables:
            if table_name not in SEEDERS:
                logger.warning("Unknown table: %s", table_name)
                continue

            seeder = SEEDERS[table_name]
            try:
                count = await seeder(session)
                await session.commit()
                logger.info("  ✓ %-20s %3d rows inserted", table_name, count)
            except Exception as exc:
                await session.rollback()
                logger.error("  ✗ %-20s ERROR: %s", table_name, exc)

    await engine.dispose()
    logger.info("Seeding complete.")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Seed CarTrawler database")
    parser.add_argument(
        "--table",
        choices=list(SEEDERS.keys()),
        help="Seed only this table (default: all tables)",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop all tables before seeding (DESTRUCTIVE!)",
    )
    args = parser.parse_args()

    tables = [args.table] if args.table else SEED_ORDER

    if args.drop:
        confirm = input("This will DROP all tables. Type 'yes' to confirm: ")
        if confirm.strip().lower() != "yes":
            logger.info("Aborted.")
            return

    asyncio.run(_run(tables, drop=args.drop))


if __name__ == "__main__":
    main()
