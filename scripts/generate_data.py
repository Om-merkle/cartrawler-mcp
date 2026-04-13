"""Generate 200 rows of realistic dummy data for all CSV files."""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
random.seed(42)

# ── Reference data ─────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Arjun","Priya","Rahul","Sneha","Vikram","Ananya","Kiran","Deepa","Suresh","Meera",
    "Aditya","Pooja","Rohit","Kavya","Sanjay","Lakshmi","Manish","Nisha","Rajesh","Divya",
    "Amit","Neha","Vijay","Sunita","Ravi","Anjali","Sunil","Rekha","Arun","Smita",
    "Nikhil","Preeti","Saurabh","Pallavi","Gaurav","Shruti","Varun","Nandita","Ashish","Payal",
    "Sameer","Shweta","Tarun","Geeta","Pranav","Poornima","Vivek","Jyoti","Harish","Sangeeta",
    "Krishna","Uma","Naveen","Vidya","Ramesh","Sudha","Ajay","Madhuri","Manoj","Savita",
    "Dinesh","Usha","Kamal","Hema","Hemant","Sushma","Girish","Shankar","Chetan","Dhruv",
    "Disha","Esha","Farhan","Gopal","Govind","Harsha","Himanshu","Isha","Jagdish","Janki",
    "Jatin","Jayesh","Kapil","Ketan","Komal","Kunal","Lata","Mahesh","Manju","Milind",
    "Mohit","Mukesh","Namrata","Narayan","Neelam","Nitin","Omkar","Parag","Parth","Poonam",
    "Prasad","Pratik","Rachna","Rajan","Ranjit","Rita","Rohini","Sachin","Sandip","Sangita",
    "Sapna","Satish","Sejal","Shalini","Snehal","Sonam","Subhash","Swati","Tanvi","Tushar",
    "Umesh","Vandana","Vaishali","Vishal","Yogesh","Yash","Zara","Trupti","Sejal","Urvi",
    "Parth","Mrunal","Kedar","Aishwarya","Bhavesh","Ruchika","Tejas","Shefali","Chirag","Nidhi"
]

LAST_NAMES = [
    "Sharma","Patel","Verma","Nair","Singh","Gupta","Kumar","Menon","Reddy","Joshi",
    "Bose","Khanna","Rao","Mehta","Iyer","Tiwari","Agarwal","Pillai","Chauhan","Mishra",
    "Pandey","Shah","Desai","Chavan","Patil","Kulkarni","Jain","Kapoor","Malhotra","Saxena",
    "Srivastava","Tripathi","Dubey","Yadav","Choudhary","Banerjee","Chatterjee","Das","Ghosh","Sen",
    "Roy","Garg","Goyal","Mittal","Khandelwal","Bhatt","Vyas","Trivedi","Modi","Thakkar",
    "Parekh","Dixit","Bhat","Kamath","Shetty","Hegde","Poojary","Thomas","George","Joseph",
    "Mathew","Philip","Abraham","Chacko","Nambiar","Varma","Pillai","Naidu","Murthy","Prasad"
]

CITIES = ["Mumbai","Delhi","Bangalore","Chennai","Hyderabad","Kolkata","Pune",
          "Goa","Jaipur","Ahmedabad","Lucknow","Kochi","Chandigarh","Bhopal","Nagpur",
          "Surat","Indore","Coimbatore","Visakhapatnam","Patna",
          "Dubai","London","New York","Los Angeles","Singapore","Paris","Sydney","Bangkok","Amsterdam","Tokyo"]

IATA = {
    "Mumbai":"BOM","Delhi":"DEL","Bangalore":"BLR","Chennai":"MAA",
    "Hyderabad":"HYD","Kolkata":"CCU","Pune":"PNQ","Goa":"GOI",
    "Jaipur":"JAI","Ahmedabad":"AMD","Lucknow":"LKO","Kochi":"COK",
    "Chandigarh":"IXC","Bhopal":"BHO","Nagpur":"NAG","Surat":"STV",
    "Indore":"IDR","Coimbatore":"CJB","Visakhapatnam":"VTZ","Patna":"PAT",
    "Dubai":"DXB","London":"LHR","New York":"JFK","Los Angeles":"LAX",
    "Singapore":"SIN","Paris":"CDG","Sydney":"SYD","Bangkok":"BKK",
    "Amsterdam":"AMS","Tokyo":"NRT"
}

AIRLINES = [
    ("IndiGo","6E"),("Air India","AI"),("SpiceJet","SG"),
    ("Vistara","UK"),("GoAir","G8"),("Akasa Air","QP"),("Air Asia","I5")
]

AIRCRAFT = ["Airbus A320","Boeing 737","Airbus A320neo","Boeing 737-800",
            "ATR 72","Airbus A321","Boeing 777","Airbus A319"]

CAR_VENDORS = ["Zoomcar","Revv","Myles","Savaari","Avis","MyChoize","EasyCab","CarTrawler",
               "Hertz","Enterprise","Budget","Sixt","Europcar"]

CAR_TYPES = ["Sedan","SUV","Hatchback","Luxury","MUV","Compact"]

CAR_MODELS = {
    "Hatchback": ["Maruti Swift","Hyundai i20","Honda Jazz","Tata Tiago","Maruti Wagon R",
                  "Maruti Celerio","Hyundai Santro","Maruti Alto"],
    "Sedan":     ["Honda City","Maruti Swift Dzire","Hyundai Verna","Toyota Etios",
                  "Maruti Ciaz","Volkswagen Vento","Honda Amaze","Ford Aspire"],
    "Compact":   ["Hyundai i20","Maruti Baleno","Tata Altroz","Honda Jazz",
                  "Volkswagen Polo","Skoda Rapid","Renault Triber"],
    "SUV":       ["Mahindra Scorpio","Toyota Fortuner","Hyundai Creta","Kia Seltos",
                  "MG Hector","Mahindra XUV500","Tata Harrier","Jeep Compass"],
    "MUV":       ["Toyota Innova","Maruti Ertiga","Mahindra Marazzo","Kia Carnival",
                  "Toyota Innova Crysta","Maruti XL6"],
    "Luxury":    ["Mercedes C-Class","BMW 3 Series","Audi A4","Mercedes E-Class",
                  "BMW 5 Series","Jaguar XE","Volvo S90"],
}

HOTEL_BRANDS = {5: ["Taj","ITC","Oberoi","Marriott","Hyatt","Leela","JW Marriott","The Ritz-Carlton"],
                4: ["Novotel","Radisson Blu","Holiday Inn","Sheraton","DoubleTree","Lemon Tree Premier","Aloft"],
                3: ["Ibis","FabHotel","OYO Rooms","Treebo","Citrus","Ginger","Keys Hotels"],
                2: ["OYO","Zostel","Backpacker Panda","The Hosteller","Stop N Sleep"]}

HOTEL_AMENITIES_BY_STAR = {
    5: ["wifi","pool","gym","spa","restaurant","bar","concierge","parking","airport_shuttle","butler"],
    4: ["wifi","pool","gym","restaurant","bar","parking","airport_shuttle"],
    3: ["wifi","restaurant","gym","parking"],
    2: ["wifi","lounge","lockers"],
}

PAYMENT_METHODS = ["CARD","UPI","WALLET","NET_BANKING"]
BOOKING_STATUSES = ["CONFIRMED","PENDING","CANCELLED","COMPLETED"]
PAYMENT_STATUSES = ["PAID","PENDING","REFUNDED"]
LOYALTY_TIERS = ["BRONZE","BRONZE","BRONZE","SILVER","SILVER","GOLD","PLATINUM"]
GENDERS = ["Male","Female"]
CHANNELS = ["MOBILE_APP","WEB","WHATSAPP_BOT","VOICE_ASSISTANT"]
INTENTS = ["book_flight","book_car","book_combo","search_flights","ask_faq",
           "cancel_booking","check_offers","ask_refund","check_booking"]
COUPON_CODES = ["WELCOME10","FLYHI15","CAR10","WEEKEND15","GOA20","LUXURY20",
                "SAVE200","FIRST300","SILVER200","GOLD500","MUMBAI10","DELHI10",""]

def rand_date(start_days=30, end_days=180):
    base = date(2026, 4, 13)
    return base + timedelta(days=random.randint(start_days, end_days))

def rand_past_date(start_days=1, end_days=30):
    base = date(2026, 4, 13)
    return base - timedelta(days=random.randint(start_days, end_days))

def rand_time(hour_min=5, hour_max=22):
    h = random.randint(hour_min, hour_max)
    m = random.choice([0, 15, 30, 45])
    return f"{h:02d}:{m:02d}:00"

# ── 1. USERS ──────────────────────────────────────────────────────────────────

def gen_users():
    rows = []
    used = set()
    for i in range(200):
        uid = f"U{1001+i}"
        fn = random.choice(FIRST_NAMES)
        ln = random.choice(LAST_NAMES)
        name = f"{fn} {ln}"
        email_base = f"{fn.lower()}.{ln.lower()}{i}"
        email = f"{email_base}@email.com"
        phone = f"+91-98{random.randint(10000000,99999999)}"
        age = random.randint(21, 60)
        gender = random.choice(GENDERS)
        city = random.choice(CITIES)
        car_pref = random.choice(CAR_TYPES)
        airline_pref = random.choice([a[0] for a in AIRLINES])
        tier = random.choice(LOYALTY_TIERS)
        points = {"BRONZE": random.randint(0,999), "SILVER": random.randint(1000,2499),
                  "GOLD": random.randint(2500,4999), "PLATINUM": random.randint(5000,20000)}[tier]
        rows.append([uid,name,email,phone,age,gender,"Indian",car_pref,airline_pref,
                     city,tier,points])
    return rows

# ── 2. FLIGHTS ────────────────────────────────────────────────────────────────

ROUTES = [
    ("BOM","DEL","Mumbai","Delhi"),("DEL","BOM","Delhi","Mumbai"),
    ("DEL","BLR","Delhi","Bangalore"),("BLR","DEL","Bangalore","Delhi"),
    ("BOM","BLR","Mumbai","Bangalore"),("BLR","BOM","Bangalore","Mumbai"),
    ("MAA","BOM","Chennai","Mumbai"),("BOM","MAA","Mumbai","Chennai"),
    ("HYD","DEL","Hyderabad","Delhi"),("DEL","HYD","Delhi","Hyderabad"),
    ("CCU","DEL","Kolkata","Delhi"),("DEL","CCU","Delhi","Kolkata"),
    ("PNQ","DEL","Pune","Delhi"),("DEL","PNQ","Delhi","Pune"),
    ("BOM","GOI","Mumbai","Goa"),("GOI","BOM","Goa","Mumbai"),
    ("DEL","JAI","Delhi","Jaipur"),("JAI","DEL","Jaipur","Delhi"),
    ("BOM","AMD","Mumbai","Ahmedabad"),("AMD","BOM","Ahmedabad","Mumbai"),
    ("MAA","DEL","Chennai","Delhi"),("DEL","MAA","Delhi","Chennai"),
    ("MAA","BLR","Chennai","Bangalore"),("BLR","MAA","Bangalore","Chennai"),
    ("HYD","BOM","Hyderabad","Mumbai"),("BOM","HYD","Mumbai","Hyderabad"),
    ("CCU","BLR","Kolkata","Bangalore"),("BLR","CCU","Bangalore","Kolkata"),
    ("DEL","LKO","Delhi","Lucknow"),("LKO","DEL","Lucknow","Delhi"),
    ("BOM","CCU","Mumbai","Kolkata"),("CCU","BOM","Kolkata","Mumbai"),
    ("BLR","HYD","Bangalore","Hyderabad"),("HYD","BLR","Hyderabad","Bangalore"),
    ("DEL","COK","Delhi","Kochi"),("COK","DEL","Kochi","Delhi"),
    ("BOM","JAI","Mumbai","Jaipur"),("JAI","BOM","Jaipur","Mumbai"),
    ("HYD","MAA","Hyderabad","Chennai"),("MAA","HYD","Chennai","Hyderabad"),
]

DURATIONS = {
    ("BOM","DEL"):135,("DEL","BOM"):130,("DEL","BLR"):165,("BLR","DEL"):160,
    ("BOM","BLR"):115,("BLR","BOM"):110,("MAA","BOM"):115,("BOM","MAA"):120,
    ("HYD","DEL"):165,("DEL","HYD"):160,("CCU","DEL"):140,("DEL","CCU"):145,
    ("PNQ","DEL"):140,("DEL","PNQ"):135,("BOM","GOI"):65,("GOI","BOM"):70,
    ("DEL","JAI"):55,("JAI","DEL"):60,("BOM","AMD"):65,("AMD","BOM"):70,
    ("MAA","DEL"):180,("DEL","MAA"):175,("MAA","BLR"):75,("BLR","MAA"):80,
    ("HYD","BOM"):110,("BOM","HYD"):105,("CCU","BLR"):165,("BLR","CCU"):170,
    ("DEL","LKO"):70,("LKO","DEL"):75,("BOM","CCU"):195,("CCU","BOM"):190,
    ("BLR","HYD"):75,("HYD","BLR"):70,("DEL","COK"):210,("COK","DEL"):215,
    ("BOM","JAI"):90,("JAI","BOM"):85,("HYD","MAA"):75,("MAA","HYD"):70,
}

def gen_flights():
    rows = []
    fno_counter = {}
    for i in range(200):
        fid = f"F{4001+i}"
        route = ROUTES[i % len(ROUTES)]
        src, dst, src_city, dst_city = route
        airline, code = AIRLINES[i % len(AIRLINES)]
        fno_counter[code] = fno_counter.get(code, 100) + random.randint(1,20)
        fnum = f"{code}-{fno_counter[code]}"
        dep = rand_time()
        dur = DURATIONS.get((src,dst), random.randint(60,240))
        # calculate arrival
        dep_h, dep_m = int(dep[:2]), int(dep[3:5])
        arr_mins = dep_h*60 + dep_m + dur
        arr_h = (arr_mins // 60) % 24
        arr_m = arr_mins % 60
        arr = f"{arr_h:02d}:{arr_m:02d}:00"
        eco = random.choice([2100,2500,2800,3200,3600,3800,4200,4500,4800,5200,5800,6200])
        biz = eco * random.randint(2,3)
        stops = random.choices([0,1],[0.85,0.15])[0]
        aircraft = random.choice(AIRCRAFT)
        seats = random.randint(80,200)
        baggage = random.choice([15,15,20,20,25])
        refund = random.choice(["true","true","false"])
        meal = random.choice(["true","false","false"])
        wifi = random.choice(["true","false","false"])
        rows.append([fid,airline,fnum,src,dst,src_city,dst_city,dep,arr,dur,
                     eco,biz,stops,aircraft,seats,baggage,refund,meal,wifi])
    return rows

# ── 3. CARS ───────────────────────────────────────────────────────────────────

CITY_LOCATIONS = {
    "Mumbai": ["Mumbai Airport T2","Bandra Kurla Complex","Andheri East","Navi Mumbai","Dadar"],
    "Delhi": ["IGI Airport T3","Connaught Place","Aerocity","Noida","Gurugram"],
    "Bangalore": ["Kempegowda Airport","MG Road","Electronic City","Whitefield","Koramangala"],
    "Chennai": ["Chennai Airport","Anna Nagar","Velachery","T Nagar","OMR"],
    "Hyderabad": ["Rajiv Gandhi Airport","Hitech City","Gachibowli","Banjara Hills","Secunderabad"],
    "Kolkata": ["Netaji Subhas Airport","Park Street","Salt Lake","Howrah","New Town"],
    "Pune": ["Pune Airport","Koregaon Park","Hinjewadi","Shivajinagar","Kothrud"],
    "Goa": ["Goa Airport","Panaji","Calangute","Baga","Panjim"],
    "Jaipur": ["Jaipur Airport","MI Road","Pink City","Vaishali Nagar","C-Scheme"],
    "Ahmedabad": ["Sardar Vallabhbhai Airport","CG Road","Navrangpura","Vastrapur","SG Highway"],
    "Kochi": ["Kochi Airport","MG Road","Kakkanad","Ernakulam","Marine Drive"],
    "Chandigarh": ["Chandigarh Airport","Sector 17","Sector 35","Phase 1","Mohali"],
    "Nagpur": ["Nagpur Airport","Sitabuldi","Dharampeth","Ramdaspeth","Civil Lines"],
    "Lucknow": ["Lucknow Airport","Hazratganj","Gomti Nagar","Alambagh","Indiranagar"],
    "Dubai": ["Dubai International Airport T3","Dubai Mall","DIFC","Jumeirah Beach","Downtown Dubai","Dubai Marina","Palm Jumeirah"],
    "London": ["Heathrow Airport T5","Gatwick Airport","London Bridge","Canary Wharf","Paddington","Victoria Station","King's Cross"],
    "New York": ["JFK Airport","LaGuardia Airport","Manhattan Midtown","Times Square","Brooklyn","Queens","Newark Airport"],
    "Los Angeles": ["LAX Airport","Hollywood","Beverly Hills","Santa Monica","Downtown LA","Burbank Airport","Long Beach"],
    "Singapore": ["Changi Airport T1","Marina Bay Sands","Orchard Road","Sentosa Island","Jurong East","Bugis Junction"],
    "Paris": ["Charles de Gaulle Airport","Orly Airport","Champs-Élysées","Louvre","Montparnasse","La Défense","Eiffel Tower Area"],
    "Sydney": ["Sydney Airport","Sydney CBD","Bondi Beach","Darling Harbour","North Sydney","Parramatta","Manly"],
    "Bangkok": ["Suvarnabhumi Airport","Don Mueang Airport","Sukhumvit","Silom","Chatuchak","Asok","Nana"],
    "Amsterdam": ["Schiphol Airport","Amsterdam Centraal","Dam Square","Leidseplein","Zuidas","Westergasfabriek"],
    "Tokyo": ["Narita Airport","Haneda Airport T3","Shinjuku","Shibuya","Akihabara","Ginza","Roppongi"],
}

CITY_DIST = {
    "Mumbai":20,"Delhi":20,"Bangalore":15,"Chennai":12,"Hyderabad":12,
    "Kolkata":12,"Pune":12,"Goa":15,"Jaipur":12,"Ahmedabad":12,
    "Kochi":8,"Chandigarh":8,"Nagpur":8,"Lucknow":5,
    "Dubai":15,"London":15,"New York":15,"Los Angeles":15,"Singapore":10,
    "Paris":10,"Sydney":10,"Bangkok":10,"Amsterdam":10,"Tokyo":10,
}

FUEL_TYPES_BY_CAR = {
    "Hatchback":["Petrol","CNG"],"Sedan":["Petrol","Diesel","CNG"],
    "Compact":["Petrol","Diesel"],"SUV":["Diesel","Petrol"],
    "MUV":["Diesel","Petrol"],"Luxury":["Petrol","Diesel"],
}

def gen_cars():
    rows = []
    cid = 5001
    cities_list = []
    for city, count in CITY_DIST.items():
        cities_list.extend([city]*count)
    random.shuffle(cities_list)
    cities_list = cities_list[:200]

    for city in cities_list:
        car_type = random.choice(CAR_TYPES)
        model = random.choice(CAR_MODELS[car_type])
        vendor = random.choice(CAR_VENDORS)
        locs = CITY_LOCATIONS.get(city, [f"{city} Center"])
        location = random.choice(locs)
        fuel_options = FUEL_TYPES_BY_CAR.get(car_type, ["Petrol"])
        fuel = random.choice(fuel_options)
        if fuel == "Electric":
            model = "Tata Nexon EV"
        trans = "Automatic" if car_type in ["Luxury","Compact"] and random.random()>0.4 else random.choice(["Manual","Automatic"])
        seats = 7 if car_type in ["SUV","MUV"] else 5
        ppd_map = {"Hatchback":random.randint(1100,1600),"Sedan":random.randint(1700,2400),
                   "Compact":random.randint(1400,2000),"SUV":random.randint(2800,5000),
                   "MUV":random.randint(2500,3800),"Luxury":random.randint(7000,12000)}
        ppd = ppd_map[car_type]
        pph = round(ppd/7)
        with_driver = "true" if car_type == "MUV" and random.random()>0.6 else "false"
        avail = random.choices(["true","false"],[0.85,0.15])[0]
        rating = round(random.uniform(3.5,5.0),1)
        reviews = random.randint(50,500)
        insurance = "true" if car_type in ["Luxury","SUV"] and random.random()>0.5 else "false"
        min_age = 25 if car_type in ["Luxury","SUV"] else 21
        rows.append([f"C{cid}",vendor,city,location,car_type,model,fuel,trans,seats,
                     ppd,pph,with_driver,avail,rating,reviews,"true",insurance,min_age])
        cid += 1
    return rows

# ── 4. OFFERS ─────────────────────────────────────────────────────────────────

def gen_offers():
    return [
        ["O6001","FIRST_BOOKING","WELCOME10","10% off on your first booking",10,500,1000,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6002","FLIGHT_BOOKING","FLYHI15","15% off on flights above Rs 5000",15,800,5000,"ALL","FLIGHT","2026-01-01","2026-12-31","true"],
        ["O6003","CAR_BOOKING","CAR10","10% off on car rentals",10,400,1500,"ALL","CAR","2026-01-01","2026-12-31","true"],
        ["O6004","WEEKEND_BOOKING","WEEKEND15","15% off on weekend travel",15,1000,3000,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6005","HOLIDAY_BOOKING","GOA20","20% off on Goa bookings",20,1500,4000,"Goa","BOTH","2026-01-01","2026-12-31","true"],
        ["O6006","LOYALTY_SILVER","SILVER200","Rs 200 flat off for Silver members",0,200,2000,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6007","LOYALTY_GOLD","GOLD500","Rs 500 flat off for Gold members",0,500,3000,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6008","LOYALTY_PLATINUM","VIP500","Rs 500 off for Platinum members",0,500,0,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6009","MONSOON_SALE","MONSOON25","25% off on monsoon travel",25,2000,5000,"ALL","FLIGHT","2026-06-01","2026-09-30","true"],
        ["O6010","LUXURY_CAR","LUXURY20","20% off on Luxury car rentals",20,3000,8000,"ALL","CAR","2026-01-01","2026-12-31","true"],
        ["O6011","DELHI_SPECIAL","DELHI10","10% off on Delhi bookings",10,600,2500,"Delhi","BOTH","2026-01-01","2026-12-31","true"],
        ["O6012","MUMBAI_SPECIAL","MUMBAI10","10% off on Mumbai bookings",10,600,2500,"Mumbai","BOTH","2026-01-01","2026-12-31","true"],
        ["O6013","FLAT_SAVE","SAVE200","Flat Rs 200 off on bookings above Rs 2000",0,200,2000,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6014","NEW_YEAR","NEWYEAR30","30% off on New Year travel",30,3000,8000,"ALL","BOTH","2025-12-25","2026-01-10","false"],
        ["O6015","FIRST_FLIGHT","FIRST300","Rs 300 off on first flight booking",0,300,1500,"ALL","FLIGHT","2026-01-01","2026-12-31","true"],
        ["O6016","SUMMER_SALE","SUMMER12","12% off on advance summer bookings",12,800,3000,"ALL","BOTH","2026-04-01","2026-06-30","true"],
        ["O6017","BANGALORE_SPECIAL","BLR15","15% off on Bangalore bookings",15,900,3000,"Bangalore","BOTH","2026-01-01","2026-12-31","true"],
        ["O6018","COMBO_DEAL","COMBO10","10% off on flight+car combo bookings",10,1000,5000,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6019","EV_OFFER","GOGREEN15","15% off on Electric car rentals",15,500,2000,"ALL","CAR","2026-01-01","2026-12-31","true"],
        ["O6020","EARLY_BIRD","EARLY12","12% off when booking 30+ days in advance",12,700,2500,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6021","BUSINESS_CLASS","BIZUPGRADE","Rs 1000 off on Business class bookings",0,1000,10000,"ALL","FLIGHT","2026-01-01","2026-12-31","true"],
        ["O6022","HYDERABAD_SPECIAL","HYD10","10% off on Hyderabad bookings",10,600,2500,"Hyderabad","BOTH","2026-01-01","2026-12-31","true"],
        ["O6023","CHENNAI_SPECIAL","MAA10","10% off on Chennai bookings",10,600,2500,"Chennai","BOTH","2026-01-01","2026-12-31","true"],
        ["O6024","LOYALTY_BONUS","LOYALTY5","5% extra loyalty points on all bookings",5,300,1000,"ALL","BOTH","2026-01-01","2026-12-31","true"],
        ["O6025","STUDENT_OFFER","STUDENT10","10% off for students (age 18-25)",10,500,1500,"ALL","BOTH","2026-01-01","2026-12-31","true"],
    ]

# ── 5. HOTELS ─────────────────────────────────────────────────────────────────

HOTEL_AREAS = {
    "Mumbai":    ["Colaba","Andheri","Juhu","Bandra","Powai","Goregaon","Lower Parel","Worli"],
    "Delhi":     ["Janpath","Aerocity","Connaught Place","Karol Bagh","Dwarka","Saket","Vasant Kunj","Paharganj"],
    "Bangalore": ["Airport Road","Whitefield","Koramangala","MG Road","Indiranagar","Electronic City","Hebbal","Marathahalli"],
    "Chennai":   ["Mount Road","Nungambakkam","T Nagar","Adyar","Anna Nagar","Airport","Besant Nagar","Velachery"],
    "Hyderabad": ["Hitec City","Banjara Hills","Jubilee Hills","Secunderabad","Begumpet","Gachibowli","Ameerpet","Kukatpally"],
    "Kolkata":   ["Park Street","Salt Lake","New Town","Howrah","Esplanade","Alipore","Rajarhat","Bhowanipore"],
    "Pune":      ["Kharadi","Koregaon Park","Hinjewadi","Kalyani Nagar","Shivajinagar","Viman Nagar","Baner","Camp"],
    "Goa":       ["Calangute","Baga","Anjuna","Vagator","Candolim","Panjim","Colva","Margao","Sinquerim","Dona Paula"],
    "Jaipur":    ["Civil Lines","Pink City","Vaishali Nagar","Malviya Nagar","Sindhi Camp","Tonk Road","Mansarovar"],
    "Ahmedabad": ["CG Road","SG Highway","Vastrapur","Navrangpura","Satellite","Bodakdev","Maninagar"],
    "Kochi":     ["MG Road","Kakkanad","Ernakulam","Edapally","Marine Drive","Vyttila"],
    "Chandigarh":["Sector 17","Sector 35","Sector 22","Mohali","Panchkula","Sector 43"],
}

HOTEL_NAME_PREFIXES = {
    5: ["Taj","ITC","Oberoi","Marriott","Hyatt","Leela","JW Marriott","Four Seasons","St Regis"],
    4: ["Novotel","Radisson Blu","Holiday Inn","Sheraton","DoubleTree","Lemon Tree Premier","Aloft","Courtyard"],
    3: ["Ibis","FabHotel","Ginger","Keys Hotels","Fortune","WelcomHotel","Park Inn","Citrus"],
    2: ["OYO","Treebo","Zostel","Backpacker Panda","The Hosteller","FabExpress"],
}

PRICE_BY_STAR = {5:(12000,25000),4:(6000,12000),3:(2500,6000),2:(800,2500)}

def gen_hotels():
    rows = []
    hid = 9001
    city_counts = {
        "Mumbai":22,"Delhi":22,"Bangalore":20,"Chennai":18,"Hyderabad":18,
        "Kolkata":15,"Pune":18,"Goa":25,"Jaipur":15,"Ahmedabad":15,
        "Kochi":12,"Chandigarh":10
    }
    for city, count in city_counts.items():
        areas = HOTEL_AREAS.get(city, [city])
        for j in range(count):
            star = random.choices([5,4,3,2],[0.15,0.30,0.40,0.15])[0]
            prefix = random.choice(HOTEL_NAME_PREFIXES[star])
            name = f"{prefix} {city}"
            area = areas[j % len(areas)]
            address = f"{random.randint(1,200)} {area}, {city}"
            pmin, pmax = PRICE_BY_STAR[star]
            price = random.randint(pmin, pmax)
            price = (price // 500) * 500
            base_amenities = HOTEL_AMENITIES_BY_STAR[star].copy()
            random.shuffle(base_amenities)
            amenities = json.dumps(base_amenities[:random.randint(3, len(base_amenities))])
            total_rooms = random.choice([30,45,60,80,100,150,200,250,300,400,500])
            avail_rooms = random.randint(5, total_rooms//3)
            is_active = "true"
            rows.append([f"H{hid}",name,city,area,address,star,price,
                         amenities,total_rooms,avail_rooms,"14:00","12:00","",is_active])
            hid += 1
    return rows[:200]

# ── 6. BOOKINGS ───────────────────────────────────────────────────────────────

def gen_bookings(n_users=200, n_flights=200, n_cars=200):
    rows = []
    booking_types = ["FLIGHT_ONLY"]*80 + ["CAR_ONLY"]*60 + ["COMBO"]*60
    random.shuffle(booking_types)

    for i in range(200):
        bid = f"B{7001+i}"
        uid = f"U{random.randint(1001, 1000+n_users)}"
        btype = booking_types[i]
        travel = rand_date(20, 150)
        booking_date = rand_past_date(1, 20)
        coupon = random.choice(COUPON_CODES)
        payment = random.choice(PAYMENT_METHODS)

        if btype == "FLIGHT_ONLY":
            fid = f"F{random.randint(4001, 4000+n_flights)}"
            fprice = random.choice([2200,2800,3200,3600,4100,4500,4800,5200,5800,6200])
            discount = round(fprice * 0.1) if coupon else 0
            total = fprice - discount
            status = random.choices(BOOKING_STATUSES,[0.7,0.15,0.1,0.05])[0]
            pstatus = "REFUNDED" if status=="CANCELLED" else ("PAID" if status!="PENDING" else "PENDING")
            rows.append([bid,uid,btype,fid,fprice,"","","",travel,"",discount,total,
                         status,pstatus,payment,coupon,booking_date,
                         rand_past_date(1,5) if status=="CANCELLED" else ""])

        elif btype == "CAR_ONLY":
            cid = f"C{random.randint(5001, 5000+n_cars)}"
            days = random.randint(1,7)
            ppd = random.choice([1200,1500,1800,2200,2500,3200,4500,9000])
            cprice = ppd * days
            discount = round(cprice * 0.1) if coupon else 0
            total = cprice - discount
            ret = travel + timedelta(days=days)
            status = random.choices(BOOKING_STATUSES,[0.7,0.15,0.1,0.05])[0]
            pstatus = "REFUNDED" if status=="CANCELLED" else ("PAID" if status!="PENDING" else "PENDING")
            rows.append([bid,uid,btype,"","",cid,days,cprice,travel,ret,discount,total,
                         status,pstatus,payment,coupon,booking_date,
                         rand_past_date(1,5) if status=="CANCELLED" else ""])

        else:  # COMBO
            fid = f"F{random.randint(4001, 4000+n_flights)}"
            cid = f"C{random.randint(5001, 5000+n_cars)}"
            fprice = random.choice([3200,3800,4200,4800,5200,5800,6200])
            days = random.randint(2,7)
            ppd = random.choice([1500,1800,2200,2800,3500,9000])
            cprice = ppd * days
            discount = round((fprice+cprice) * 0.1) if coupon else 0
            total = fprice + cprice - discount
            ret = travel + timedelta(days=days)
            status = random.choices(BOOKING_STATUSES,[0.7,0.15,0.1,0.05])[0]
            pstatus = "REFUNDED" if status=="CANCELLED" else ("PAID" if status!="PENDING" else "PENDING")
            rows.append([bid,uid,btype,fid,fprice,cid,days,cprice,travel,ret,discount,total,
                         status,pstatus,payment,coupon,booking_date,
                         rand_past_date(1,5) if status=="CANCELLED" else ""])
    return rows

# ── 7. SEARCH LOGS ────────────────────────────────────────────────────────────

def gen_search_logs(n_users=200):
    rows = []
    for i in range(200):
        sid = f"SR{3001+i}"
        uid = f"U{random.randint(1001, 1000+n_users)}"
        route = random.choice(ROUTES)
        src, dst, src_city, dst_city = route
        travel = rand_date(10, 120)
        ret = (travel + timedelta(days=random.randint(2,10))) if random.random()>0.6 else ""
        passengers = random.choice([1,1,1,2,2,3])
        cabin = random.choices(["Economy","Business"],[0.85,0.15])[0]
        inc_car = random.choices(["true","false"],[0.35,0.65])[0]
        car_pref = random.choice(CAR_TYPES) if inc_car=="true" else ""
        budget = random.choice([3000,5000,8000,12000,20000,50000]) if random.random()>0.3 else ""
        results = random.randint(0,15)
        created = f"2026-04-{random.randint(1,12):02d}T{random.randint(7,22):02d}:{random.randint(0,59):02d}:00"
        rows.append([sid,uid,src,dst,src_city,dst_city,travel,ret,passengers,cabin,
                     inc_car,car_pref,budget,results,created])
    return rows

# ── 8. SESSIONS ───────────────────────────────────────────────────────────────

def gen_sessions(n_users=200):
    rows = []
    for i in range(200):
        sid = f"S{2001+i}"
        uid = f"U{random.randint(1001, 1000+n_users)}"
        channel = random.choice(CHANNELS)
        intent = random.choice(INTENTS)
        ctx = {}
        if "flight" in intent or "combo" in intent:
            r = random.choice(ROUTES)
            ctx = {"source": r[0], "destination": r[1]}
            if "combo" in intent:
                ctx["car_type"] = random.choice(CAR_TYPES)
        elif "car" in intent:
            ctx = {"city": random.choice(CITIES), "car_type": random.choice(CAR_TYPES)}
        elif "faq" in intent:
            ctx = {"question": random.choice(["cancellation policy","refund status",
                    "baggage allowance","loyalty points","minimum age car rental",
                    "payment methods","coupon codes","hotel check-in time"])}
        elif "cancel" in intent:
            ctx = {"booking_id": f"B{random.randint(7001,7200)}"}
        elif "offers" in intent:
            ctx = {"booking_type": random.choice(["FLIGHT","CAR","BOTH"])}
        resolved = random.choices(["true","false"],[0.85,0.15])[0]
        duration = random.randint(60, 900)
        created = f"2026-04-{random.randint(1,12):02d}T{random.randint(7,22):02d}:{random.randint(0,59):02d}:00"
        rows.append([sid,uid,channel,intent,json.dumps(ctx),resolved,duration,created])
    return rows

# ── 9. KNOWLEDGE BASE ─────────────────────────────────────────────────────────

KB_EXTRA = [
    ["K8031","flight_booking","IndiGo is India's largest airline by market share offering budget-friendly Economy flights. Air India is the national carrier providing full-service meals and more baggage. SpiceJet offers competitive pricing especially for short routes. Vistara (a Tata-Singapore Airlines JV) is known for premium Economy and Business class experience. Akasa Air is the newest entrant with modern Boeing 737 MAX fleet.",False,"faq","en","2026-01-20"],
    ["K8032","flight_booking","CarTrawler displays real-time seat availability. Green = available, Yellow = filling fast (< 10 seats), Red = last 3 seats. Prices may change dynamically. We recommend booking immediately when you see your preferred fare. Price lock feature available for Rs 99 to hold a fare for 24 hours.",False,"faq","en","2026-01-20"],
    ["K8033","car_rental","One-way car rentals: Some vendors allow picking up in one city and dropping off in another. One-way charges (Rs 500-2000) apply. Available routes: Mumbai-Pune, Delhi-Agra, Delhi-Jaipur, Bangalore-Mysore, Chennai-Pondicherry. Advance booking of 48 hours required for one-way rentals.",False,"faq","en","2026-01-20"],
    ["K8034","car_rental","Corporate car rental packages: CarTrawler offers special rates for corporate clients booking 10+ vehicles per month. Monthly invoicing, dedicated account manager, and priority vehicle allocation available. Contact corporate@cartrawler.in for rates. GST invoices provided for all corporate bookings.",False,"faq","en","2026-01-20"],
    ["K8035","cancellation","How to cancel a booking on CarTrawler: Go to My Bookings, select the booking you want to cancel, click Cancel Booking. Cancellation reason required for refund processing. Refund timeline: Refundable tickets 5-7 business days, non-refundable credit note within 24 hours, car rentals 3-5 business days.",False,"faq","en","2026-01-20"],
    ["K8036","loyalty","How to check loyalty points: Log in to your CarTrawler account, go to Profile > Loyalty Points. Points history shows all earned and redeemed transactions. Points summary shows current balance, tier, and points needed for next tier upgrade.",False,"faq","en","2026-01-20"],
    ["K8037","hotel","Hotel star rating guide: 5-star (luxury, premium amenities, fine dining), 4-star (upscale, business amenities, good restaurants), 3-star (mid-scale, comfortable rooms, basic amenities), 2-star (budget, basic rooms, essential amenities). All hotels on CarTrawler are physically verified.",False,"faq","en","2026-01-20"],
    ["K8038","hotel","Hotel booking process on CarTrawler: Search by city, select dates and guests, filter by star rating or amenities, compare options, click Book Now. No additional hotel booking fees. Direct booking rates guaranteed. Free cancellation on most hotels up to 24 hours before check-in. Premium hotels may require non-refundable advance.",False,"faq","en","2026-01-20"],
    ["K8039","travel_tips","Cheapest time to book flights: Book domestic Indian flights 4-6 weeks in advance for best fares. Last-minute flights (1-3 days before) can be very expensive. Tuesday and Wednesday are cheapest travel days. Early morning (6-8 AM) and late night (10 PM+) flights are typically 15-20% cheaper than peak-time flights.",False,"faq","en","2026-01-20"],
    ["K8040","travel_tips","Packing tips for Indian domestic travel: Carry government-issued photo ID (Aadhaar/PAN/Passport) - mandatory for flights. Pack light for IndiGo/SpiceJet as extra baggage is expensive. Carry a portable charger. Download airline app and CarTrawler app for offline access to booking details. Arrive at airport 90 minutes before departure for domestic flights.",False,"faq","en","2026-01-20"],
    ["K8041","payment","EMI options on CarTrawler: EMI available on bookings above Rs 10,000 using HDFC, ICICI, SBI, Axis, Kotak credit cards. 3-month EMI at 0% interest on select cards. 6 and 12-month options available at bank's standard interest rates. EMI option shown at checkout for eligible cards.",False,"faq","en","2026-01-20"],
    ["K8042","support","Escalation process: Level 1 - Chat/WhatsApp support (5 min response). Level 2 - Phone support 1800-CARTRAWLER (immediate). Level 3 - Email escalation support@cartrawler.in (4 hour response). For urgent issues (flight in 2 hours, car not available), always call the helpline directly for fastest resolution.",False,"faq","en","2026-01-20"],
    ["K8043","flight_booking","Popular business travel routes: Delhi-Mumbai (most popular, hourly flights), Delhi-Bangalore (popular IT corridor), Mumbai-Hyderabad, Delhi-Hyderabad. Business class upgrades available at check-in subject to availability. Vistara and Air India have the best Business class experience on domestic routes.",False,"faq","en","2026-01-20"],
    ["K8044","car_rental","Best car for each use: City travel = Hatchback or Compact (easy to park, fuel efficient). Airport transfer = Sedan (comfortable, spacious boot). Family road trip = SUV or MUV (space, ground clearance). Corporate meetings = Sedan or Luxury. Goa/hill station = SUV recommended. Group travel (7+) = MUV.",False,"faq","en","2026-01-20"],
    ["K8045","offers","How to maximize savings on CarTrawler: Combine COMBO10 (10% off flight+car) with a loyalty discount for maximum savings. MONSOON25 valid June-September offers highest discount. Book during CarTrawler sale events (Diwali, Holi, Independence Day) for extra offers. Loyalty PLATINUM members get automatic 15% off.",False,"faq","en","2026-01-20"],
    ["K8046","airport_info","Goa (Dabolim) airport information: IATA code GOI. Located in South Goa. Takes 30-45 minutes to North Goa beaches like Calangute, Baga. Pre-paid taxi counters available. Peak season October-March sees heavy traffic - pre-book car rental. New Mopa airport (IATA: GOX) in North Goa also operational.",False,"faq","en","2026-01-20"],
    ["K8047","airport_info","Bangalore Kempegowda International Airport: IATA BLR. Located 35 km from city center. Namma Metro connectivity available to Airport from 2025. Car rental counters in Arrivals area. Prepaid taxi counter available. Rush hour (8-10 AM, 5-8 PM) adds 60-90 minutes to city travel time.",False,"faq","en","2026-01-20"],
    ["K8048","cancellation","No-show policy: If you do not board a flight and did not cancel, the ticket is marked as no-show. For refundable tickets, no-show forfeits the full fare. For non-refundable tickets, no refund or credit note is issued. Car rental no-show results in full day charge. Always cancel if you cannot travel.",False,"faq","en","2026-01-20"],
    ["K8049","loyalty","Tier upgrade timeline: Bronze to Silver when you cross 1000 points. Silver to Gold at 2500 points. Gold to Platinum at 5000 points. Tier is calculated on rolling 12-month basis. Tier benefits apply from the date of upgrade. Downgrade happens if points fall below tier threshold during annual review.",False,"faq","en","2026-01-20"],
    ["K8050","travel_tips","Monsoon travel tips (June-September): Book refundable tickets as weather can cause flight delays. Carry waterproof bags for electronics. Goa, Kerala, and hill stations are beautiful during monsoon but have limited connectivity. Avoid night driving in mountainous regions during monsoon. Check weather forecasts 24 hours before departure.",False,"faq","en","2026-01-20"],
    ["K8051","car_rental","International car rental at CarTrawler: Available in UAE, UK, USA, Singapore, France, Australia, Thailand, Netherlands, and Japan. Prices shown in local currency. Valid international driving licence (IDL) required in most countries. UK/Australia/Japan drive on the LEFT side. Minimum age: 21 in most countries, 25 in USA for some vehicle classes.",False,"faq","en","2026-01-20"],
    ["K8052","car_rental","Dubai car rental rules: Minimum age 21, valid passport + UAE visa required for tourists. No-alcohol policy strictly enforced — DUI results in licence confiscation. Speed cameras everywhere — fines auto-charged to credit card. Salik (toll) charges apply on major roads. Petrol is cheap (~AED 2.6/litre).",False,"faq","en","2026-01-20"],
    ["K8053","car_rental","London car rental rules: Drive on the LEFT. Minimum age 21 (under-25 surcharge applies). Congestion Charge £15/day applies in central London (Mon-Fri 7AM-6PM). Ultra Low Emission Zone (ULEZ) charges £12.50/day for older vehicles. Most rentals include insurance but check excess amounts.",False,"faq","en","2026-01-20"],
    ["K8054","car_rental","USA car rental rules: Minimum age 21 (25 for luxury at some vendors). International licence recommended alongside home country licence. Fuel sold in gallons. Drive on the RIGHT. Toll roads common — many vendors offer EZ-Pass/toll transponders. CDW (Collision Damage Waiver) insurance recommended.",False,"faq","en","2026-01-20"],
    ["K8055","car_rental","Singapore car rental rules: Drive on the LEFT. Electronic Road Pricing (ERP) tolls apply in city centre during peak hours. Minimum age 22. Car rentals include basic insurance; additional coverage available. Parking coupons required for coupon parking zones. Expressways are fast — budget 30 min from Changi Airport to city centre.",False,"faq","en","2026-01-20"],
]

# ── WRITE FILES ────────────────────────────────────────────────────────────────

def write_csv(filename, header, rows):
    path = DATA_DIR / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"[ok] {filename:30s} {len(rows)} rows")

if __name__ == "__main__":
    print("Generating data files...")

    write_csv("users.csv",
        ["user_id","name","email","phone","age","gender","nationality","preferred_car_type",
         "preferred_airline","home_city","loyalty_tier","loyalty_points"],
        gen_users())

    write_csv("flights.csv",
        ["flight_id","airline","flight_number","source","destination","source_city",
         "destination_city","departure_time","arrival_time","duration_mins","price_economy",
         "price_business","stops","aircraft","available_seats","baggage_kg","refundable",
         "meal_included","wifi_available"],
        gen_flights())

    cars = gen_cars()
    write_csv("cars.csv",
        ["car_id","vendor","city","pickup_location","car_type","car_model","fuel_type",
         "transmission","seating_capacity","price_per_day","price_per_hour","with_driver",
         "availability","rating","total_reviews","ac","insurance_included","min_age_required"],
        cars)

    write_csv("offers.csv",
        ["offer_id","trigger_event","coupon_code","description","discount_percentage",
         "max_discount_amount","min_booking_amount","valid_city","applicable_on",
         "valid_from","valid_till","is_active"],
        gen_offers())

    hotels = gen_hotels()
    write_csv("hotels.csv",
        ["hotel_id","name","city","area","address","star_rating","price_per_night","amenities",
         "total_rooms","available_rooms","check_in_time","check_out_time","image_url","is_active"],
        hotels)

    write_csv("bookings.csv",
        ["booking_id","user_id","booking_type","flight_id","flight_price","car_id","rental_days",
         "car_price","travel_date","return_date","discount_applied","total_price","status",
         "payment_status","payment_method","coupon_code","booking_date","cancellation_date"],
        gen_bookings())

    write_csv("search_logs.csv",
        ["search_id","user_id","source","destination","source_city","destination_city",
         "travel_date","return_date","passengers","cabin_class","include_car",
         "car_type_preference","budget_max","search_result_count","created_at"],
        gen_search_logs())

    write_csv("sessions.csv",
        ["session_id","user_id","channel","intent","context","resolved",
         "session_duration_secs","created_at"],
        gen_sessions())

    # Knowledge base: read existing rows (skip any already in KB_EXTRA) + append 20 new ones
    kb_path = DATA_DIR / "knowledge_base.csv"
    kb_rows = []
    extra_ids = {row[0] for row in KB_EXTRA}
    if kb_path.exists():
        with open(kb_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            kb_rows.extend([row for row in reader if row[0] not in extra_ids])
    kb_rows.extend(KB_EXTRA)
    write_csv("knowledge_base.csv",
        ["kb_id","topic","content","embedding_ready","chunk_type","language","last_updated"],
        kb_rows)

    print("\nAll done! Re-seed the database with:")
    print("  echo yes| uv run python scripts/seed_db.py --drop")
