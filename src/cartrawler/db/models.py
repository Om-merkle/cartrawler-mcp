"""SQLAlchemy ORM models — mapped 1-to-1 from the provided CSV schema."""
from datetime import date, datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────
class User(Base):
    """Application users — combines CSV users.csv + auth fields."""

    __tablename__ = "users"

    user_id = Column(String(10), primary_key=True, index=True)  # e.g. U1001
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20))
    age = Column(Integer)
    gender = Column(String(10))
    nationality = Column(String(50))
    preferred_car_type = Column(String(50))
    preferred_airline = Column(String(100))
    home_city = Column(String(100))
    loyalty_tier = Column(String(20), default="BRONZE")  # BRONZE/SILVER/GOLD/PLATINUM
    loyalty_points = Column(Integer, default=0)

    # Auth fields (not in CSV — added for the auth system)
    hashed_password = Column(String(255), nullable=True)  # nullable for seed data
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    refresh_token = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    bookings = relationship("Booking", back_populates="user", lazy="noload")
    search_logs = relationship("SearchLog", back_populates="user", lazy="noload")
    sessions = relationship("UserSession", back_populates="user", lazy="noload")


# ─────────────────────────────────────────────────────────────────────────────
# Flights
# ─────────────────────────────────────────────────────────────────────────────
class Flight(Base):
    """Available flights — from flights.csv."""

    __tablename__ = "flights"

    flight_id = Column(String(10), primary_key=True, index=True)  # e.g. F4001
    airline = Column(String(100), nullable=False)
    flight_number = Column(String(20), nullable=False)
    source = Column(String(10), nullable=False)       # IATA code
    destination = Column(String(10), nullable=False)  # IATA code
    source_city = Column(String(100))
    destination_city = Column(String(100))
    departure_time = Column(String(10))  # HH:MM:SS
    arrival_time = Column(String(10))
    duration_mins = Column(Integer)
    price_economy = Column(Float)
    price_business = Column(Float)
    stops = Column(Integer, default=0)
    aircraft = Column(String(50))
    available_seats = Column(Integer)
    baggage_kg = Column(Integer)
    refundable = Column(Boolean, default=False)
    meal_included = Column(Boolean, default=False)
    wifi_available = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_flights_source_dest", "source", "destination"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Cars / Vehicles
# ─────────────────────────────────────────────────────────────────────────────
class Car(Base):
    """Rental cars — from cars.csv."""

    __tablename__ = "cars"

    car_id = Column(String(10), primary_key=True, index=True)  # e.g. C5001
    vendor = Column(String(100))
    city = Column(String(100), nullable=False, index=True)
    pickup_location = Column(String(255))
    car_type = Column(String(50))      # Sedan/SUV/Hatchback/Luxury/MUV/Compact
    car_model = Column(String(100))
    fuel_type = Column(String(20))     # Petrol/Diesel/Electric/CNG
    transmission = Column(String(20))  # Manual/Automatic
    seating_capacity = Column(Integer)
    price_per_day = Column(Float)
    price_per_hour = Column(Float)
    with_driver = Column(Boolean, default=False)
    availability = Column(Boolean, default=True)
    rating = Column(Float)
    total_reviews = Column(Integer)
    ac = Column(Boolean, default=True)
    insurance_included = Column(Boolean, default=False)
    min_age_required = Column(Integer, default=21)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_cars_city_type", "city", "car_type"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bookings
# ─────────────────────────────────────────────────────────────────────────────
class Booking(Base):
    """Unified booking record (flight-only / car-only / combo)."""

    __tablename__ = "bookings"

    booking_id = Column(String(10), primary_key=True, index=True)  # e.g. B7001
    user_id = Column(String(10), ForeignKey("users.user_id"), nullable=False, index=True)
    booking_type = Column(String(20), nullable=False)  # COMBO/FLIGHT_ONLY/CAR_ONLY

    # Flight
    flight_id = Column(String(10), ForeignKey("flights.flight_id"), nullable=True)
    flight_price = Column(Float, nullable=True)

    # Car
    car_id = Column(String(10), ForeignKey("cars.car_id"), nullable=True)
    rental_days = Column(Integer, nullable=True)
    car_price = Column(Float, nullable=True)

    # Travel dates
    travel_date = Column(Date, nullable=False)
    return_date = Column(Date, nullable=True)

    # Pricing
    discount_applied = Column(Float, default=0)
    total_price = Column(Float, nullable=False)

    # Status
    status = Column(String(20), default="PENDING")       # PENDING/CONFIRMED/CANCELLED/COMPLETED
    payment_status = Column(String(20), default="PENDING")  # PENDING/PAID/REFUNDED
    payment_method = Column(String(30))                   # CARD/UPI/WALLET/NET_BANKING
    coupon_code = Column(String(30), nullable=True)

    # Timestamps
    booking_date = Column(Date)
    cancellation_date = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="bookings")
    flight = relationship("Flight", lazy="noload")
    car = relationship("Car", lazy="noload")


# ─────────────────────────────────────────────────────────────────────────────
# Offers / Coupons
# ─────────────────────────────────────────────────────────────────────────────
class Offer(Base):
    """Discount offers / coupons — from offers.csv."""

    __tablename__ = "offers"

    offer_id = Column(String(10), primary_key=True, index=True)  # e.g. O6001
    trigger_event = Column(String(50))       # FIRST_BOOKING / CAR_BOOKING etc.
    coupon_code = Column(String(30), unique=True, nullable=False, index=True)
    description = Column(Text)
    discount_percentage = Column(Float)
    max_discount_amount = Column(Float)
    min_booking_amount = Column(Float)
    valid_city = Column(String(100), default="ALL")
    applicable_on = Column(String(20))       # BOTH/FLIGHT/CAR
    valid_from = Column(Date)
    valid_till = Column(Date)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ─────────────────────────────────────────────────────────────────────────────
# Search Logs
# ─────────────────────────────────────────────────────────────────────────────
class SearchLog(Base):
    """User search history — from search_logs.csv."""

    __tablename__ = "search_logs"

    search_id = Column(String(10), primary_key=True, index=True)  # e.g. SR3001
    user_id = Column(String(10), ForeignKey("users.user_id"), nullable=False, index=True)
    source = Column(String(10))
    destination = Column(String(10))
    source_city = Column(String(100))
    destination_city = Column(String(100))
    travel_date = Column(Date)
    return_date = Column(Date, nullable=True)
    passengers = Column(Integer, default=1)
    cabin_class = Column(String(20))          # Economy/Business
    include_car = Column(Boolean, default=False)
    car_type_preference = Column(String(50), nullable=True)
    budget_max = Column(Float, nullable=True)
    search_result_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="search_logs")


# ─────────────────────────────────────────────────────────────────────────────
# Sessions (Chat / App sessions)
# ─────────────────────────────────────────────────────────────────────────────
class UserSession(Base):
    """User interaction sessions — from sessions.csv."""

    __tablename__ = "user_sessions"

    session_id = Column(String(10), primary_key=True, index=True)  # e.g. S2001
    user_id = Column(String(10), ForeignKey("users.user_id"), nullable=False, index=True)
    channel = Column(String(30))   # MOBILE_APP/WEB/VOICE_ASSISTANT/WHATSAPP_BOT
    intent = Column(String(50))    # book_flight/cancel_booking/ask_refund etc.
    context = Column(JSONB)        # intent details stored as JSON
    resolved = Column(Boolean, default=False)
    session_duration_secs = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="sessions")


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Base (FAQ) + Vector Embeddings
# ─────────────────────────────────────────────────────────────────────────────
class KnowledgeBase(Base):
    """Raw FAQ / knowledge-base entries — from knowledge_base.csv."""

    __tablename__ = "knowledge_base"

    kb_id = Column(String(10), primary_key=True, index=True)  # e.g. K8001
    topic = Column(String(50), index=True)
    content = Column(Text, nullable=False)
    embedding_ready = Column(Boolean, default=False)
    chunk_type = Column(String(20))
    language = Column(String(10), default="en")
    last_updated = Column(Date)

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class KnowledgeBaseEmbedding(Base):
    """pgvector embeddings for RAG pipeline."""

    __tablename__ = "knowledge_base_embeddings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kb_id = Column(String(10), ForeignKey("knowledge_base.kb_id"), nullable=False, index=True)
    topic = Column(String(50), index=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # text-embedding-3-small dimension

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index(
            "ix_kb_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Hotels (stub — populated via external API or manual entry)
# ─────────────────────────────────────────────────────────────────────────────
class Hotel(Base):
    """Hotels linked to cities served by flights."""

    __tablename__ = "hotels"

    hotel_id = Column(String(20), primary_key=True)
    name = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False, index=True)
    area = Column(String(100))
    address = Column(Text)
    star_rating = Column(Float)
    price_per_night = Column(Float)
    amenities = Column(JSONB)        # ["wifi", "pool", "gym", ...]
    total_rooms = Column(Integer)
    available_rooms = Column(Integer)
    check_in_time = Column(String(10))
    check_out_time = Column(String(10))
    image_url = Column(Text)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_hotels_city_rating", "city", "star_rating"),
    )
