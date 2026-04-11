"""
LangGraph Orchestrator Agent
==============================
A ReAct-style agent that intelligently routes user queries
to the correct tool(s). Used by the MCP `agent_query` meta-tool.

Graph nodes:
  START → route_intent → [tool_node] → synthesize → END

The agent receives the user's natural language query plus optional
context (user_id, access_token) and decides which tool(s) to invoke.
"""
from __future__ import annotations

import json
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from cartrawler.config import settings

# ─────────────────────────────────────────────────────────────────────────────
# LangChain tool wrappers (thin async wrappers around our tool functions)
# ─────────────────────────────────────────────────────────────────────────────

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


# Wrap each function as a LangChain tool
@tool
async def tool_register_user(name: str, email: str, password: str, phone: str = "", home_city: str = "") -> str:
    """Register a new user. Returns JWT tokens on success."""
    result = await register_user(name=name, email=email, password=password, phone=phone or None, home_city=home_city or None)
    return json.dumps(result)


@tool
async def tool_login_user(email: str, password: str) -> str:
    """Authenticate user with email + password. Returns JWT access and refresh tokens."""
    result = await login_user(email=email, password=password)
    return json.dumps(result)


@tool
async def tool_get_profile(access_token: str) -> str:
    """Get authenticated user profile using access token."""
    result = await get_profile(access_token=access_token)
    return json.dumps(result)


@tool
async def tool_search_flights(
    source: str = "",
    destination: str = "",
    source_city: str = "",
    destination_city: str = "",
    cabin_class: str = "Economy",
    max_price: float = 0,
    max_stops: int = -1,
    airline: str = "",
    refundable_only: bool = False,
) -> str:
    """Search available flights by route, price, stops, airline."""
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
    )
    return json.dumps(result)


@tool
async def tool_get_flight_details(flight_id: str) -> str:
    """Get detailed info for a specific flight by flight_id (e.g. F4001)."""
    result = await get_flight_details(flight_id=flight_id)
    return json.dumps(result)


@tool
async def tool_book_flight(
    access_token: str,
    flight_id: str,
    travel_date: str,
    cabin_class: str = "Economy",
    payment_method: str = "CARD",
    coupon_code: str = "",
) -> str:
    """Book a flight for the authenticated user."""
    result = await book_flight(
        access_token=access_token,
        flight_id=flight_id,
        travel_date=travel_date,
        cabin_class=cabin_class,
        payment_method=payment_method,
        coupon_code=coupon_code or None,
    )
    return json.dumps(result)


@tool
async def tool_get_booking_details(access_token: str, booking_id: str) -> str:
    """Get details for a specific booking by booking_id."""
    result = await get_booking_details(access_token=access_token, booking_id=booking_id)
    return json.dumps(result)


@tool
async def tool_list_my_bookings(access_token: str, status_filter: str = "", booking_type: str = "") -> str:
    """List all bookings for the authenticated user."""
    result = await list_my_bookings(
        access_token=access_token,
        status_filter=status_filter or None,
        booking_type=booking_type or None,
    )
    return json.dumps(result)


@tool
async def tool_cancel_booking(access_token: str, booking_id: str) -> str:
    """Cancel a booking and check refund eligibility."""
    result = await cancel_booking(access_token=access_token, booking_id=booking_id)
    return json.dumps(result)


@tool
async def tool_search_cars(
    city: str,
    car_type: str = "",
    fuel_type: str = "",
    transmission: str = "",
    max_price_per_day: float = 0,
    vendor: str = "",
    min_rating: float = 0,
) -> str:
    """Search available rental cars in a city. CarTrawler min age: 21."""
    result = await search_cars(
        city=city,
        car_type=car_type or None,
        fuel_type=fuel_type or None,
        transmission=transmission or None,
        max_price_per_day=max_price_per_day or None,
        vendor=vendor or None,
        min_rating=min_rating or None,
    )
    return json.dumps(result)


@tool
async def tool_book_car(
    access_token: str,
    car_id: str,
    pickup_date: str,
    rental_days: int,
    payment_method: str = "CARD",
    coupon_code: str = "",
) -> str:
    """Book a rental car for authenticated user. Fuel not included. Security deposit at pickup."""
    result = await book_car(
        access_token=access_token,
        car_id=car_id,
        pickup_date=pickup_date,
        rental_days=rental_days,
        payment_method=payment_method,
        coupon_code=coupon_code or None,
    )
    return json.dumps(result)


@tool
async def tool_search_rides(access_token: str, city: str = "", travel_date: str = "", status_filter: str = "") -> str:
    """Search all ride/car bookings for authenticated user (airport transfers, local travel)."""
    result = await search_rides(
        access_token=access_token,
        city=city or None,
        travel_date=travel_date or None,
        status_filter=status_filter or None,
    )
    return json.dumps(result)


@tool
async def tool_search_hotels(
    city: str,
    area: str = "",
    min_rating: float = 0,
    max_price_per_night: float = 0,
) -> str:
    """Search hotels at flight destination by city, area, rating, price."""
    result = await search_hotels(
        city=city,
        area=area or None,
        min_rating=min_rating or None,
        max_price_per_night=max_price_per_night or None,
    )
    return json.dumps(result)


@tool
async def tool_get_all_offers(applicable_on: str = "BOTH", city: str = "") -> str:
    """Get all active discount offers and coupons."""
    result = await get_all_offers(applicable_on=applicable_on or None, city=city or None)
    return json.dumps(result)


@tool
async def tool_validate_coupon(coupon_code: str, booking_amount: float, applicable_on: str = "BOTH", city: str = "") -> str:
    """Validate a coupon code and compute the discount."""
    result = await validate_coupon(
        coupon_code=coupon_code,
        booking_amount=booking_amount,
        applicable_on=applicable_on,
        city=city or None,
    )
    return json.dumps(result)


@tool
async def tool_answer_faq(question: str) -> str:
    """Answer FAQ about CarTrawler services. No login required. RAG-powered."""
    result = await answer_faq(question=question)
    return json.dumps(result)


# ─────────────────────────────────────────────────────────────────────────────
# All tools list
# ─────────────────────────────────────────────────────────────────────────────

ALL_TOOLS = [
    tool_register_user,
    tool_login_user,
    tool_get_profile,
    tool_search_flights,
    tool_get_flight_details,
    tool_book_flight,
    tool_get_booking_details,
    tool_list_my_bookings,
    tool_cancel_booking,
    tool_search_cars,
    tool_book_car,
    tool_search_rides,
    tool_search_hotels,
    tool_get_all_offers,
    tool_validate_coupon,
    tool_answer_faq,
]


# ─────────────────────────────────────────────────────────────────────────────
# Graph State
# ─────────────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    context: dict[str, Any]   # access_token, user_id etc.


# ─────────────────────────────────────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_MESSAGE = """You are a professional travel assistant for CarTrawler — India's leading flight and car rental booking platform.

You have access to tools for:
- User registration and login (register_user, login_user)
- Flight search and booking (search_flights, book_flight, get_booking_details)
- Car and vehicle rental (search_cars, book_car, search_rides)
- Hotel search by destination (search_hotels)
- Discounts and coupons (get_all_offers, validate_coupon)
- FAQ answers about policies (answer_faq) — no login required

Available airlines: IndiGo, Air India, SpiceJet, Vistara, GoAir, Go First, AirAsia India, Akasa Air, StarAir.

IMPORTANT RULES:
1. Always ask for login/register BEFORE attempting bookings.
2. Use the access_token from login for all booking operations.
3. When searching flights, accept city names OR IATA codes.
4. For car rentals, always mention the minimum age (21), security deposit, and fuel policy.
5. Apply applicable coupons automatically when booking if the user mentions them.
6. For FAQs, answer immediately without requiring login.
7. Be concise and professional. Always confirm booking details before proceeding.
"""


def _build_graph():
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
        openai_api_key=settings.openai_api_key,
    ).bind_tools(ALL_TOOLS)

    tool_node = ToolNode(ALL_TOOLS)

    def agent_node(state: AgentState) -> AgentState:
        messages = state["messages"]
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_MESSAGE)] + list(messages)
        response = llm.invoke(messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


# Module-level compiled graph (lazy)
_graph = None


def get_agent():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

async def run_agent(
    query: str,
    access_token: str | None = None,
    conversation_history: list[dict] | None = None,
) -> dict:
    """
    Run the LangGraph agent with a natural language query.

    Args:
        query: User's natural language query
        access_token: JWT token if the user is already logged in
        conversation_history: Previous messages [{"role": "user/assistant", "content": "..."}]

    Returns: {"success": bool, "response": str, "tool_calls": list}
    """
    messages = []

    # Inject prior conversation
    if conversation_history:
        for msg in conversation_history[-10:]:  # keep last 10 turns
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            else:
                messages.append(AIMessage(content=content))

    # Add token context hint if available
    if access_token:
        query = f"[Context: I have an active session. Access token: {access_token}]\n\n{query}"

    messages.append(HumanMessage(content=query))

    graph = get_agent()
    try:
        result = await graph.ainvoke({"messages": messages, "context": {}})
        final_msg = result["messages"][-1]
        response_text = final_msg.content if hasattr(final_msg, "content") else str(final_msg)

        # Collect tool calls for transparency
        tool_calls = []
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tool_calls.extend([tc["name"] for tc in msg.tool_calls])

        return {
            "success": True,
            "response": response_text,
            "tool_calls": tool_calls,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "response": f"Agent error: {exc}",
            "tool_calls": [],
        }
