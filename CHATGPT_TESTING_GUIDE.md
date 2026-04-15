# CarTrawler MCP — ChatGPT Testing Guide

Paste these queries into ChatGPT after connecting the CarTrawler MCP connector.
Each query maps to a specific tool. The **Tool called** column shows what you should
see in ChatGPT's tool-use panel.

---

## Prerequisites

1. Connect CarTrawler in ChatGPT (Apps → Add → paste your server URL).
2. Complete the OAuth login/create-account screen.
3. Run `POST /admin/seed` (once) so sample data exists in the database.
4. Run `POST /admin/embed` to build the FAQ knowledge base.

---

## 1. Account — No Auth Needed for Search/FAQ

### Start here — these must work WITHOUT logging in

| Query to paste | Tool called | Expected result |
|---|---|---|
| `Search for rental cars in Mumbai` | `find_cars` | List of cars with prices, vendors, ratings |
| `Find SUV cars in Goa` | `find_cars` | SUV listings in Goa |
| `Show me electric cars in Bengaluru` | `find_cars` | CNG/Electric cars |
| `Get details for car C5001` | `car_details` | Full car spec card |
| `What offers are available?` | `car_offers` | Coupon codes + discounts |
| `What is the cancellation policy?` | `faq` | Policy answer from knowledge base |
| `What is the minimum age to rent a car?` | `faq` | "21 years (25 for Luxury/SUV)" |

> **If none of these trigger a tool call**, the MCP connector is not properly connected.
> Disconnect and re-add the connector in ChatGPT settings.

---

## 2. Authentication Flow

### 2.1 Register a new account
```
Register me as a new user.
Name: Rahul Sharma
Email: rahul@test.com
Password: Test@123
Phone: 9876543210
City: Mumbai
```
**Tool called:** `register`
**Expect:** Welcome card + User ID + loyalty tier BRONZE shown.

### 2.2 Login with existing credentials
```
Log me in. Email: rahul@test.com  Password: Test@123
```
**Tool called:** `login`
**Expect:** "Welcome back, Rahul Sharma!" + access token displayed.

### 2.3 View profile (after login)
```
Show me my profile / account details.
```
**Tool called:** `my_profile`
**Expect:** Name, email, loyalty tier, points, home city card.

> If ChatGPT says "please log in first" → say your email + password → it will call
> `login` automatically, then immediately call `my_profile`.

### 2.4 Refresh session
```
Refresh my session tokens.
```
**Tool called:** `refresh_session`
**Expect:** New access token issued, valid for 30 min.

### 2.5 Logout
```
Log me out.
```
**Tool called:** `logout`
**Expect:** "Logged Out" confirmation.

---

## 3. Car Search — `find_cars`

All queries below call `find_cars`. No login required.

| Query | Filter applied |
|---|---|
| `Find cars in Mumbai` | city only |
| `Find automatic SUVs in Goa` | car_type=SUV, transmission=Automatic |
| `Show petrol cars in Delhi under ₹3000 per day` | fuel_type=Petrol, max_price_per_day=3000 |
| `Find cars with a driver in Hyderabad` | with_driver=True |
| `Show Zoomcar options in Pune` | vendor=Zoomcar |
| `Cars in Chennai rated above 4.5` | min_rating=4.5 |
| `Find insured cars in Jaipur` | insurance_included=True |
| `Search for cars in Antarctica` | — (no results case) |

---

## 4. Car Details — `car_details`

| Query | Expect |
|---|---|
| `Get full details for car C5001` | Full spec card — model, vendor, price, fuel, insurance |
| `Tell me about car C9999` | "Car not found" error |

---

## 5. Book a Car — `book_rental_car`

Requires login. ChatGPT will ask for credentials if not already logged in.

### 5.1 Standard booking
```
Book car C5001 from 2026-05-10 for 3 days. Pay by card.
```
**Tool called:** `login` (if needed) → `book_rental_car`
**Expect:** Booking confirmed card with Booking ID, dates, total price, loyalty points earned.

### 5.2 Booking with coupon
```
Book car C5002 from 2026-05-15 for 2 days. Use coupon FIRST20.
```
**Expect:** Discount applied in the confirmation card.

### 5.3 Unavailable car (book C5001 again after 5.1)
```
Book car C5001 from 2026-06-01 for 1 day.
```
**Expect:** "Car is not available" error.

---

## 6. My Bookings & Rides

Requires login.

| Query | Tool called | Expect |
|---|---|---|
| `Show all my bookings` | `my_bookings` | Table of bookings with dates, status, total |
| `Show my confirmed bookings` | `my_bookings` | Filtered to CONFIRMED only |
| `Show my cancelled bookings` | `my_bookings` | Filtered to CANCELLED |
| `Show my rides` | `my_rides` | Airport transfer / city ride bookings |
| `Show my rides in Mumbai` | `my_rides` | Rides filtered to Mumbai |

---

## 7. Cancel a Booking — `cancel_booking`

Requires login.

| Query | Expect |
|---|---|
| `Cancel booking B7301` | Cancellation confirmed + refund timeline |
| `Cancel booking B7301` *(again)* | "Already CANCELLED" error |
| `Cancel booking B0001` | "Booking not found" error |

---

## 8. Offers & Coupons

No login required.

| Query | Tool called | Expect |
|---|---|---|
| `What car rental offers are available?` | `car_offers` | All active coupons with discount % |
| `Show offers in Mumbai` | `car_offers` | Mumbai-specific + ALL-city offers |
| `Is coupon FIRST20 valid for ₹5000?` | `validate_car_coupon` | Valid + computed discount + final price |
| `Check if FAKECODE works for ₹4000` | `validate_car_coupon` | Invalid coupon error |
| `What's the best offer for a ₹8000 booking in Goa?` | `best_car_offer` | Ranked offers with max savings highlighted |

---

## 9. FAQ — `faq`

No login required. All answered by RAG pipeline.

| Query |
|---|
| `What is the cancellation policy?` |
| `How does the loyalty points system work?` |
| `What is the minimum age to rent a car?` |
| `Is there a security deposit for rentals?` |
| `Is fuel included in the rental price?` |
| `Is insurance included or do I need to buy it?` |
| `What payment methods are accepted?` |
| `How long do refunds take?` |
| `Can I pick up a car from the airport?` |
| `Does CarTrawler offer helicopter rentals?` |

---

## 10. Full End-to-End Smoke Test

Run these in one ChatGPT conversation in order:

```
1. Search for SUV cars in Goa.
2. Get details for the first car in the list.
3. What offers are available for Goa bookings?
4. Register me as Priya Mehta, priya@test.com, password Pass@123, age 27, city Goa.
5. Book that car from 2026-06-01 for 3 days. Use the best coupon you found.
6. Show all my bookings.
7. What is the cancellation policy?
8. Cancel my booking.
9. Show my profile and loyalty points.
10. Log out.
```

---

## 11. Flight & Hotel Redirect (Out-of-Scope)

| Query | Tool called | Expect |
|---|---|---|
| `Find me a flight from Mumbai to Goa` | `find_flights` | Flight booking links (Kayak, IndiGo) + car rental pitch |
| `Book me a hotel in Goa` | `find_hotels` | Hotel booking links (Booking.com, OYO) + car rental pitch |

---

## Tool Reference (Actual Registered Names)

| Tool name | Auth? | What it does |
|---|---|---|
| `register` | No | Create new CarTrawler account |
| `login` | No | Authenticate, returns access_token |
| `refresh_session` | No (needs refresh_token) | Renew access_token |
| `my_profile` | **Yes** | View name, email, loyalty tier, points |
| `logout` | **Yes** | Invalidate session |
| `find_cars` | No | Search available rental cars by city/filters |
| `car_details` | No | Full info for a specific car ID |
| `book_rental_car` | **Yes** | Book a car, returns booking confirmation |
| `my_bookings` | **Yes** | List all car rental bookings |
| `cancel_booking` | **Yes** | Cancel a booking + refund |
| `my_rides` | **Yes** | List airport transfer / ride bookings |
| `car_offers` | No | List all active coupon codes |
| `best_car_offer` | No | Find best coupon for a booking amount |
| `validate_car_coupon` | No | Check if a coupon is valid + compute discount |
| `faq` | No | Answer questions about CarTrawler policies |
| `find_flights` | No | Redirect to flight apps |
| `find_hotels` | No | Redirect to hotel apps |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| **No tool called at all** for any query | Disconnect & re-add MCP connector in ChatGPT; verify server is running at `/health` |
| **"show my profile" returns text, no tool** | Say your email + password — ChatGPT will login then call `my_profile` |
| **"search cars" returns text, no tool** | The MCP connection is broken — check server logs |
| **"Registration failed: password error"** | Fixed — bcrypt now uses direct library, no passlib |
| **OAuth / login page error** | Run `POST /admin/seed` to initialise the database |
| **FAQ returns empty answers** | Run `POST /admin/embed` to build the vector store |

---

## Policy Reference

| Rule | Detail |
|---|---|
| Minimum driver age | 21 years (Luxury/SUV: 25 years) |
| Security deposit | ₹2,000–10,000 collected at pickup (refundable) |
| Fuel | NOT included in rental price |
| Cancellation | ≥ 2 hours before pickup = full refund |
| Loyalty: Bronze | 0–999 points |
| Loyalty: Silver | 1,000–4,999 points |
| Loyalty: Gold | 5,000–9,999 points |
| Loyalty: Platinum | 10,000+ points |
| Points earned | floor(total_price / 100) per booking |
