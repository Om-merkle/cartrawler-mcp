"""
CarTrawler MCP Tool Tests
==========================
Pytest test suite for all major tool functions.
Uses an in-memory SQLite database (via SQLAlchemy) for fast, isolated tests.

Run:
    uv run pytest tests/ -v
    uv run pytest tests/ -v -k "auth"
    uv run pytest tests/ --tb=short
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

# ─────────────────────────────────────────────────────────────────────────────
# Test database setup (in-memory SQLite)
# ─────────────────────────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def test_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    # Import here to avoid triggering DB connections at import time
    from cartrawler.db.models import Base

    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(test_engine):
    """Provide an async DB session backed by the test engine."""
    async with AsyncSession(test_engine) as session:
        yield session


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — seed data
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
async def seeded_db(db_session):
    """
    Seed a minimal set of rows: 1 user, 2 flights, 2 cars, 2 offers.
    Returns the session for additional queries.
    """
    from cartrawler.auth.password import hash_password
    from cartrawler.db.models import Car, Flight, Offer, User

    user = User(
        user_id="U1001",
        name="Test User",
        email="test@example.com",
        hashed_password=hash_password("Password123!"),
        phone="+91-9999999999",
        age=28,
        home_city="Mumbai",
        loyalty_tier="BRONZE",
        loyalty_points=0,
        is_active=True,
        is_verified=True,
    )

    flight1 = Flight(
        flight_id="F4001",
        airline="IndiGo",
        flight_number="6E-201",
        source="BOM",
        destination="DEL",
        source_city="Mumbai",
        destination_city="Delhi",
        departure_time="06:00:00",
        arrival_time="08:15:00",
        duration_mins=135,
        price_economy=4500.0,
        price_business=12000.0,
        stops=0,
        available_seats=50,
        baggage_kg=15,
        refundable=True,
        meal_included=False,
        wifi_available=True,
    )

    flight2 = Flight(
        flight_id="F4002",
        airline="SpiceJet",
        flight_number="SG-301",
        source="DEL",
        destination="BOM",
        source_city="Delhi",
        destination_city="Mumbai",
        departure_time="09:00:00",
        arrival_time="11:15:00",
        duration_mins=135,
        price_economy=3800.0,
        price_business=10000.0,
        stops=0,
        available_seats=0,  # sold out
        baggage_kg=15,
        refundable=False,
        meal_included=False,
        wifi_available=False,
    )

    car1 = Car(
        car_id="C5001",
        vendor="Zoomcar",
        city="Mumbai",
        car_type="Sedan",
        car_model="Maruti Swift Dzire",
        fuel_type="Petrol",
        transmission="Manual",
        seating_capacity=5,
        price_per_day=1800.0,
        availability=True,
        rating=4.2,
        min_age_required=21,
        insurance_included=False,
    )

    car2 = Car(
        car_id="C5002",
        vendor="Myles",
        city="Delhi",
        car_type="Luxury",
        car_model="BMW 3 Series",
        fuel_type="Petrol",
        transmission="Automatic",
        seating_capacity=5,
        price_per_day=9000.0,
        availability=True,
        rating=4.8,
        min_age_required=25,
        insurance_included=True,
    )

    offer = Offer(
        offer_id="O6001",
        coupon_code="WELCOME10",
        description="10% off first booking",
        discount_percentage=10.0,
        max_discount_amount=500.0,
        min_booking_amount=1000.0,
        valid_city="ALL",
        applicable_on="BOTH",
        valid_from=date.today() - timedelta(days=10),
        valid_till=date.today() + timedelta(days=90),
        is_active=True,
    )

    db_session.add_all([user, flight1, flight2, car1, car2, offer])
    await db_session.commit()
    return db_session


# ─────────────────────────────────────────────────────────────────────────────
# Auth tools
# ─────────────────────────────────────────────────────────────────────────────

class TestAuthTools:
    """Tests for cartrawler.tools.auth_tools"""

    @pytest.mark.asyncio
    async def test_register_user_success(self, test_engine):
        from cartrawler.tools.auth_tools import register_user

        with patch("cartrawler.tools.auth_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            # No existing user
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_result2 = MagicMock()
            mock_result2.fetchall.return_value = []
            mock_session.execute = AsyncMock(side_effect=[mock_result, mock_result2])
            mock_session.commit = AsyncMock()

            result = await register_user(
                name="Alice",
                email="alice@example.com",
                password="SecurePass123!",
            )

        assert result["success"] is True
        assert "Alice" in result["message"]
        assert result["tokens"]["token_type"] == "bearer"
        assert result["tokens"]["loyalty_tier"] == "BRONZE"

    @pytest.mark.asyncio
    async def test_register_user_duplicate_email(self):
        from cartrawler.db.models import User
        from cartrawler.tools.auth_tools import register_user

        existing_user = MagicMock(spec=User)
        existing_user.email = "dupe@example.com"

        with patch("cartrawler.tools.auth_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = existing_user
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await register_user(
                name="Bob",
                email="dupe@example.com",
                password="Pass123!",
            )

        assert result["success"] is False
        assert "already registered" in result["message"]

    @pytest.mark.asyncio
    async def test_login_success(self):
        from cartrawler.auth.password import hash_password
        from cartrawler.db.models import User
        from cartrawler.tools.auth_tools import login_user

        mock_user = MagicMock(spec=User)
        mock_user.user_id = "U1001"
        mock_user.name = "Test User"
        mock_user.email = "test@example.com"
        mock_user.hashed_password = hash_password("correct_password")
        mock_user.is_active = True
        mock_user.loyalty_tier = "SILVER"
        mock_user.loyalty_points = 1500

        with patch("cartrawler.tools.auth_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()

            result = await login_user(email="test@example.com", password="correct_password")

        assert result["success"] is True
        assert "Welcome back" in result["message"]
        assert result["tokens"]["user_id"] == "U1001"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self):
        from cartrawler.auth.password import hash_password
        from cartrawler.db.models import User
        from cartrawler.tools.auth_tools import login_user

        mock_user = MagicMock(spec=User)
        mock_user.hashed_password = hash_password("correct_password")
        mock_user.is_active = True

        with patch("cartrawler.tools.auth_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await login_user(email="test@example.com", password="wrong_password")

        assert result["success"] is False
        assert "Incorrect password" in result["message"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self):
        from cartrawler.tools.auth_tools import login_user

        with patch("cartrawler.tools.auth_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await login_user(email="nobody@example.com", password="pass")

        assert result["success"] is False
        assert "No account found" in result["message"]


# ─────────────────────────────────────────────────────────────────────────────
# JWT handler
# ─────────────────────────────────────────────────────────────────────────────

class TestJWTHandler:
    def test_create_and_verify_access_token(self):
        from cartrawler.auth.jwt_handler import create_access_token, verify_token

        token = create_access_token(subject="U1001", extra={"name": "Alice"})
        payload = verify_token(token, expected_type="access")

        assert payload["sub"] == "U1001"
        assert payload["name"] == "Alice"
        assert payload["type"] == "access"

    def test_create_and_verify_refresh_token(self):
        from cartrawler.auth.jwt_handler import create_refresh_token, verify_token

        token = create_refresh_token(subject="U1002")
        payload = verify_token(token, expected_type="refresh")

        assert payload["sub"] == "U1002"
        assert payload["type"] == "refresh"

    def test_verify_wrong_type_raises(self):
        from cartrawler.auth.jwt_handler import create_access_token, verify_token

        token = create_access_token(subject="U1001")

        with pytest.raises(ValueError, match="token type"):
            verify_token(token, expected_type="refresh")

    def test_verify_invalid_token_raises(self):
        from cartrawler.auth.jwt_handler import verify_token

        with pytest.raises(ValueError):
            verify_token("not.a.valid.token")


# ─────────────────────────────────────────────────────────────────────────────
# Password hashing
# ─────────────────────────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_and_verify(self):
        from cartrawler.auth.password import hash_password, verify_password

        hashed = hash_password("my_password")
        assert hashed != "my_password"
        assert verify_password("my_password", hashed) is True

    def test_wrong_password_fails(self):
        from cartrawler.auth.password import hash_password, verify_password

        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_different_passwords_different_hashes(self):
        from cartrawler.auth.password import hash_password

        h1 = hash_password("pass1")
        h2 = hash_password("pass1")
        # bcrypt uses salt — same input produces different hashes
        assert h1 != h2


# ─────────────────────────────────────────────────────────────────────────────
# Flight tools
# ─────────────────────────────────────────────────────────────────────────────

class TestFlightTools:
    @pytest.mark.asyncio
    async def test_search_flights_by_iata(self):
        from cartrawler.tools.flight_tools import search_flights

        mock_flights = [
            MagicMock(
                flight_id="F4001",
                airline="IndiGo",
                flight_number="6E-201",
                source="BOM",
                destination="DEL",
                source_city="Mumbai",
                destination_city="Delhi",
                departure_time="06:00:00",
                arrival_time="08:15:00",
                duration_mins=135,
                price_economy=4500.0,
                price_business=12000.0,
                stops=0,
                available_seats=50,
                baggage_kg=15,
                refundable=True,
                meal_included=False,
                wifi_available=True,
            )
        ]

        with patch("cartrawler.tools.flight_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_flights
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await search_flights(source="BOM", destination="DEL")

        assert result["success"] is True
        assert result["count"] == 1
        assert result["flights"][0]["flight_id"] == "F4001"

    @pytest.mark.asyncio
    async def test_search_flights_no_results(self):
        from cartrawler.tools.flight_tools import search_flights

        with patch("cartrawler.tools.flight_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await search_flights(source="BOM", destination="GOI")

        assert result["success"] is True
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_get_flight_details_found(self):
        from cartrawler.tools.flight_tools import get_flight_details

        mock_flight = MagicMock(
            flight_id="F4001",
            airline="IndiGo",
            flight_number="6E-201",
            source="BOM",
            destination="DEL",
            source_city="Mumbai",
            destination_city="Delhi",
            departure_time="06:00:00",
            arrival_time="08:15:00",
            duration_mins=135,
            price_economy=4500.0,
            price_business=12000.0,
            stops=0,
            aircraft="Airbus A320",
            available_seats=50,
            baggage_kg=15,
            refundable=True,
            meal_included=False,
            wifi_available=True,
        )

        with patch("cartrawler.tools.flight_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_flight
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await get_flight_details(flight_id="F4001")

        assert result["success"] is True
        assert result["flight"]["airline"] == "IndiGo"

    @pytest.mark.asyncio
    async def test_get_flight_details_not_found(self):
        from cartrawler.tools.flight_tools import get_flight_details

        with patch("cartrawler.tools.flight_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await get_flight_details(flight_id="F9999")

        assert result["success"] is False
        assert "not found" in result["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Car tools
# ─────────────────────────────────────────────────────────────────────────────

class TestCarTools:
    @pytest.mark.asyncio
    async def test_search_cars_in_city(self):
        from cartrawler.tools.car_tools import search_cars

        mock_cars = [
            MagicMock(
                car_id="C5001",
                vendor="Zoomcar",
                city="Mumbai",
                pickup_location="Airport",
                car_type="Sedan",
                car_model="Swift Dzire",
                fuel_type="Petrol",
                transmission="Manual",
                seating_capacity=5,
                price_per_day=1800.0,
                price_per_hour=250.0,
                with_driver=False,
                availability=True,
                rating=4.2,
                total_reviews=320,
                ac=True,
                insurance_included=False,
                min_age_required=21,
            )
        ]

        with patch("cartrawler.tools.car_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_cars
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await search_cars(city="Mumbai")

        assert result["success"] is True
        assert result["count"] == 1
        assert result["cars"][0]["car_id"] == "C5001"

    @pytest.mark.asyncio
    async def test_book_car_age_too_young(self):
        """User under 21 should be rejected."""
        from cartrawler.auth.jwt_handler import create_access_token
        from cartrawler.db.models import Car, User
        from cartrawler.tools.car_tools import book_car

        token = create_access_token(subject="U1001")

        mock_user = MagicMock(spec=User)
        mock_user.user_id = "U1001"
        mock_user.age = 19  # under 21

        mock_car = MagicMock(spec=Car)
        mock_car.car_id = "C5001"
        mock_car.car_type = "Sedan"
        mock_car.min_age_required = 21
        mock_car.availability = True
        mock_car.price_per_day = 1800.0

        with patch("cartrawler.tools.car_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            user_result = MagicMock()
            user_result.scalar_one_or_none.return_value = mock_user
            car_result = MagicMock()
            car_result.scalar_one_or_none.return_value = mock_car
            mock_session.execute = AsyncMock(side_effect=[user_result, car_result])

            result = await book_car(
                access_token=token,
                car_id="C5001",
                pickup_date="2026-05-15",
                rental_days=3,
            )

        assert result["success"] is False
        assert "21" in result["message"] or "age" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_book_luxury_car_age_too_young(self):
        """User under 25 should be rejected for Luxury cars."""
        from cartrawler.auth.jwt_handler import create_access_token
        from cartrawler.db.models import Car, User
        from cartrawler.tools.car_tools import book_car

        token = create_access_token(subject="U1001")

        mock_user = MagicMock(spec=User)
        mock_user.user_id = "U1001"
        mock_user.age = 23  # over 21 but under 25

        mock_car = MagicMock(spec=Car)
        mock_car.car_id = "C5021"
        mock_car.car_type = "Luxury"
        mock_car.min_age_required = 25
        mock_car.availability = True
        mock_car.price_per_day = 9000.0

        with patch("cartrawler.tools.car_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            user_result = MagicMock()
            user_result.scalar_one_or_none.return_value = mock_user
            car_result = MagicMock()
            car_result.scalar_one_or_none.return_value = mock_car
            mock_session.execute = AsyncMock(side_effect=[user_result, car_result])

            result = await book_car(
                access_token=token,
                car_id="C5021",
                pickup_date="2026-05-15",
                rental_days=2,
            )

        assert result["success"] is False
        assert "25" in result["message"] or "age" in result["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Offer tools
# ─────────────────────────────────────────────────────────────────────────────

class TestOfferTools:
    @pytest.mark.asyncio
    async def test_validate_coupon_valid(self):
        from cartrawler.tools.offer_tools import validate_coupon

        mock_offer = MagicMock(
            offer_id="O6001",
            coupon_code="WELCOME10",
            description="10% off first booking",
            discount_percentage=10.0,
            max_discount_amount=500.0,
            min_booking_amount=1000.0,
            valid_city="ALL",
            applicable_on="BOTH",
            valid_from=date.today() - timedelta(days=10),
            valid_till=date.today() + timedelta(days=90),
            is_active=True,
        )

        with patch("cartrawler.tools.offer_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_offer
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await validate_coupon(
                coupon_code="WELCOME10",
                booking_amount=5000.0,
                applicable_on="BOTH",
            )

        assert result["success"] is True
        assert result["discount_amount"] == 500.0  # 10% of 5000 capped at 500
        assert result["final_amount"] == 4500.0

    @pytest.mark.asyncio
    async def test_validate_coupon_below_minimum(self):
        from cartrawler.tools.offer_tools import validate_coupon

        mock_offer = MagicMock(
            coupon_code="WELCOME10",
            discount_percentage=10.0,
            max_discount_amount=500.0,
            min_booking_amount=2000.0,
            valid_city="ALL",
            applicable_on="BOTH",
            valid_from=date.today() - timedelta(days=10),
            valid_till=date.today() + timedelta(days=90),
            is_active=True,
        )

        with patch("cartrawler.tools.offer_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_offer
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await validate_coupon(
                coupon_code="WELCOME10",
                booking_amount=500.0,  # below minimum of 2000
                applicable_on="BOTH",
            )

        assert result["success"] is False
        assert "minimum" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_validate_coupon_not_found(self):
        from cartrawler.tools.offer_tools import validate_coupon

        with patch("cartrawler.tools.offer_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await validate_coupon(
                coupon_code="INVALID99",
                booking_amount=5000.0,
                applicable_on="BOTH",
            )

        assert result["success"] is False
        assert "not found" in result["message"].lower() or "invalid" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_get_all_offers(self):
        from cartrawler.tools.offer_tools import get_all_offers

        mock_offers = [
            MagicMock(
                offer_id="O6001",
                coupon_code="WELCOME10",
                description="10% off",
                discount_percentage=10.0,
                max_discount_amount=500.0,
                min_booking_amount=1000.0,
                valid_city="ALL",
                applicable_on="BOTH",
                valid_from=date.today() - timedelta(days=10),
                valid_till=date.today() + timedelta(days=90),
                is_active=True,
            )
        ]

        with patch("cartrawler.tools.offer_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_offers
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await get_all_offers()

        assert result["success"] is True
        assert result["count"] == 1
        assert result["offers"][0]["coupon_code"] == "WELCOME10"


# ─────────────────────────────────────────────────────────────────────────────
# Hotel tools
# ─────────────────────────────────────────────────────────────────────────────

class TestHotelTools:
    @pytest.mark.asyncio
    async def test_search_hotels_by_city(self):
        from cartrawler.tools.hotel_tools import search_hotels

        mock_hotels = [
            MagicMock(
                hotel_id="H9001",
                name="The Taj Mahal Palace",
                city="Mumbai",
                area="Colaba",
                address="Apollo Bunder, Colaba",
                star_rating=5.0,
                price_per_night=18000.0,
                amenities=["wifi", "pool", "spa"],
                available_rooms=45,
                check_in_time="14:00",
                check_out_time="12:00",
            )
        ]

        with patch("cartrawler.tools.hotel_tools.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session_cls.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_hotels
            mock_session.execute = AsyncMock(return_value=mock_result)

            result = await search_hotels(city="Mumbai")

        assert result["success"] is True
        assert result["count"] == 1
        assert result["hotels"][0]["name"] == "The Taj Mahal Palace"

    @pytest.mark.asyncio
    async def test_search_hotels_city_alias(self):
        """'bombay' should be resolved to 'Mumbai' via CITY_ALIASES."""
        from cartrawler.tools.hotel_tools import CITY_ALIASES

        assert "bombay" in CITY_ALIASES
        assert CITY_ALIASES["bombay"] == "Mumbai"

    @pytest.mark.asyncio
    async def test_search_hotels_empty_city(self):
        from cartrawler.tools.hotel_tools import search_hotels

        result = await search_hotels(city="")
        assert result["success"] is False
        assert "city" in result["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# FAQ tools
# ─────────────────────────────────────────────────────────────────────────────

class TestFAQTools:
    @pytest.mark.asyncio
    async def test_answer_faq_empty_question(self):
        from cartrawler.tools.faq_tools import answer_faq

        result = await answer_faq(question="")
        assert result["success"] is False
        assert "question" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_answer_faq_calls_pipeline(self):
        from cartrawler.tools.faq_tools import answer_faq

        mock_pipeline = AsyncMock()
        mock_pipeline.ask = AsyncMock(return_value={
            "success": True,
            "answer": "The minimum age for car rental is 21 years.",
            "sources": ["K8007"],
        })

        with patch("cartrawler.tools.faq_tools.get_faq_pipeline", return_value=mock_pipeline):
            result = await answer_faq(question="What is the minimum age for car rental?")

        assert result["success"] is True
        assert "21" in result["answer"]
        mock_pipeline.ask.assert_called_once_with("What is the minimum age for car rental?")


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────

class TestSettings:
    def test_default_values(self):
        from cartrawler.config import settings

        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_access_token_expire_minutes == 30
        assert settings.openai_model == "gpt-4o-mini"
        assert settings.embedding_dimension == 1536

    def test_data_dir_is_valid_path(self):
        from pathlib import Path

        from cartrawler.config import settings

        assert isinstance(settings.data_dir, Path)
        assert settings.data_dir.name == "data"

    def test_is_production_flag(self):
        from cartrawler.config import settings

        # In test environment, should be development
        assert settings.is_production is (settings.app_env == "production")
