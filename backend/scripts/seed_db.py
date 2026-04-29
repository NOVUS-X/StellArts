"""
Seed script to populate the database with fake artisans, clients, and bookings.
Generates 50+ artisans with realistic coordinates and specialties.
"""

import json
import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.models.artisan import Artisan
from app.models.client import Client
from app.models.booking import Booking, BookingStatus
from app.core.security import get_password_hash

# Specialty categories for artisans
SPECIALTIES = [
    ["Carpentry", "Furniture Making", "Wood Carving"],
    ["Plumbing", "Pipe Fitting", "Water Heater Installation"],
    ["Electrical", "Wiring", "Lighting Installation"],
    ["Painting", "Wall Finishing", "Decorative Painting"],
    ["Masonry", "Brick Laying", "Stone Work"],
    ["Welding", "Metal Fabrication", "Iron Work"],
    ["Roofing", "Tile Installation", "Waterproofing"],
    ["Landscaping", "Garden Design", "Irrigation Systems"],
    ["HVAC", "Air Conditioning", "Ventilation"],
    ["Tiling", "Flooring", "Ceramic Work"],
    ["Glass Work", "Window Installation", "Mirror Fitting"],
    ["Interior Design", "Space Planning", "Color Consultation"],
]

# Nigerian cities with coordinates (for realistic location data)
LOCATIONS = [
    {"city": "Lagos", "lat": 6.5244, "lon": 3.3792},
    {"city": "Abuja", "lat": 9.0579, "lon": 7.4951},
    {"city": "Port Harcourt", "lat": 4.8156, "lon": 7.0498},
    {"city": "Kano", "lat": 12.0022, "lon": 8.5920},
    {"city": "Ibadan", "lat": 7.3775, "lon": 3.9470},
    {"city": "Benin City", "lat": 6.3350, "lon": 5.6037},
    {"city": "Kaduna", "lat": 10.5222, "lon": 7.4383},
    {"city": "Enugu", "lat": 6.4403, "lon": 7.4914},
    {"city": "Calabar", "lat": 4.9517, "lon": 8.3222},
    {"city": "Jos", "lat": 9.9288, "lon": 8.8921},
    {"city": "Ilorin", "lat": 8.4966, "lon": 4.5426},
    {"city": "Abeokuta", "lat": 7.1475, "lon": 3.3619},
    {"city": "Owerri", "lat": 5.4840, "lon": 7.0346},
    {"city": "Uyo", "lat": 5.0378, "lon": 7.9085},
    {"city": "Warri", "lat": 5.5167, "lon": 5.7500},
    {"city": "Akure", "lat": 7.2571, "lon": 5.2058},
]

FIRST_NAMES = [
    "Emeka", "Chinedu", "Oluwaseun", "Adebayo", "Ibrahim", "Musa",
    "Chioma", "Ngozi", "Aisha", "Fatima", "Blessing", "Oluwakemi",
    "Kunle", "Tunde", "Obinna", "Chukwuemeka", "Yusuf", "Abubakar",
    "Nkechi", "Adaeze", "Folake", "Titilayo", "Suleiman", "Halima",
]

LAST_NAMES = [
    "Okafor", "Adeyemi", "Obi", "Nnamdi", "Balogun", "Ibrahim",
    "Olawale", "Eze", "Chukwudi", "Adebisi", "Okonkwo", "Nwankwo",
    "Abubakar", "Olatunji", "Uche", "Mohammed", "Afolabi", "Ogundimu",
]

BUSINESS_PREFIXES = [
    "Premium", "Expert", "Professional", "Quality", "Master",
    "Elite", "Superior", "Reliable", "Trusted", "Supreme",
]

BUSINESS_SUFFIXES = [
    "Works", "Services", "Crafts", "Solutions", "Enterprises",
    "Hub", "Studio", "Workshop", "Ventures", "Group",
]


def generate_artisan_data(index: int) -> dict:
    """Generate realistic artisan data."""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    location_data = random.choice(LOCATIONS)
    specialties = random.choice(SPECIALTIES)
    
    # Add slight random offset to coordinates (within ~10km)
    lat_offset = random.uniform(-0.1, 0.1)
    lon_offset = random.uniform(-0.1, 0.1)
    
    return {
        "email": f"artisan{index}.{first_name.lower()}@example.com",
        "username": f"artisan_{first_name.lower()}_{last_name.lower()}_{index}",
        "full_name": f"{first_name} {last_name}",
        "phone": f"+234{random.choice(['803', '805', '806', '810', '813', '816', '901', '903'])}{random.randint(1000000, 9999999):07d}",
        "business_name": f"{random.choice(BUSINESS_PREFIXES)} {last_name} {random.choice(BUSINESS_SUFFIXES)}",
        "description": f"Experienced {specialties[0].lower()} specialist with {random.randint(2, 20)} years of experience. Dedicated to delivering quality workmanship and customer satisfaction.",
        "specialties": specialties,
        "experience_years": random.randint(2, 20),
        "hourly_rate": Decimal(str(round(random.uniform(15.0, 150.0), 2))),
        "location": f"{location_data['city']}, Nigeria",
        "latitude": Decimal(str(round(location_data['lat'] + lat_offset, 6))),
        "longitude": Decimal(str(round(location_data['lon'] + lon_offset, 6))),
        "is_verified": random.choice([True, True, True, False]),  # 75% verified
        "is_available": random.choice([True, True, True, False]),  # 75% available
        "rating": Decimal(str(round(random.uniform(3.5, 5.0), 2))),
        "total_reviews": random.randint(0, 150),
    }


def generate_client_data(index: int) -> dict:
    """Generate realistic client data."""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    location_data = random.choice(LOCATIONS)
    
    return {
        "email": f"client{index}.{first_name.lower()}@example.com",
        "username": f"client_{first_name.lower()}_{last_name.lower()}_{index}",
        "full_name": f"{first_name} {last_name}",
        "phone": f"+234{random.choice(['803', '805', '806', '810', '813', '816', '901', '903'])}{random.randint(1000000, 9999999):07d}",
        "address": f"{random.randint(1, 500)} {random.choice(['Adetokunbo', 'Awolowo', 'Herbert Macaulay', 'Obafemi', 'Tafawa Balewa'])} Street, {location_data['city']}",
    }


def seed_database(num_artisans: int = 55, num_clients: int = 20, num_bookings: int = 100):
    """Seed the database with fake data."""
    db: Session = SessionLocal()
    
    try:
        # Clear existing data (optional - comment out if you want to keep existing data)
        print("Clearing existing seed data...")
        db.query(Booking).filter(Booking.notes.like("[SEED]%")).delete()
        db.query(Artisan).filter(Artisan.description.like("[SEED]%")).delete()
        db.query(Client).filter(Client.address.like("[SEED]%")).delete()
        db.query(User).filter(User.email.like("%@example.com")).delete()
        db.commit()
        
        print(f"Creating {num_artisans} artisans...")
        artisans = []
        for i in range(num_artisans):
            artisan_data = generate_artisan_data(i)
            
            # Create user
            user = User(
                email=artisan_data["email"],
                username=artisan_data["username"],
                full_name=artisan_data["full_name"],
                phone=artisan_data["phone"],
                hashed_password=get_password_hash("password123"),
                role="artisan",
                is_active=True,
                is_verified=artisan_data["is_verified"],
            )
            db.add(user)
            db.flush()
            
            # Create artisan profile
            artisan = Artisan(
                user_id=user.id,
                business_name=artisan_data["business_name"],
                description=f"[SEED] {artisan_data['description']}",
                specialties=json.dumps(artisan_data["specialties"]),
                experience_years=artisan_data["experience_years"],
                hourly_rate=artisan_data["hourly_rate"],
                location=artisan_data["location"],
                latitude=artisan_data["latitude"],
                longitude=artisan_data["longitude"],
                is_verified=artisan_data["is_verified"],
                is_available=artisan_data["is_available"],
                rating=artisan_data["rating"],
                total_reviews=artisan_data["total_reviews"],
                last_active=datetime.utcnow() - timedelta(hours=random.randint(0, 72)),
            )
            db.add(artisan)
            artisans.append(artisan)
        
        db.commit()
        print(f"✓ Created {len(artisans)} artisans")
        
        print(f"Creating {num_clients} clients...")
        clients = []
        for i in range(num_clients):
            client_data = generate_client_data(i)
            
            # Create user
            user = User(
                email=client_data["email"],
                username=client_data["username"],
                full_name=client_data["full_name"],
                phone=client_data["phone"],
                hashed_password=get_password_hash("password123"),
                role="client",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            db.flush()
            
            # Create client profile
            client = Client(
                user_id=user.id,
                address=f"[SEED] {client_data['address']}",
                preferred_contact=random.choice(["email", "phone"]),
            )
            db.add(client)
            clients.append(client)
        
        db.commit()
        print(f"✓ Created {len(clients)} clients")
        
        print(f"Creating {num_bookings} bookings...")
        bookings = []
        for i in range(num_bookings):
            client = random.choice(clients)
            artisan = random.choice(artisans)
            
            # Get artisan specialties
            artisan_specialties = json.loads(artisan.specialties)
            service = random.choice(artisan_specialties)
            
            estimated_hours = Decimal(str(round(random.uniform(2.0, 40.0), 2)))
            labor_cost = artisan.hourly_rate * estimated_hours
            material_cost = Decimal(str(round(random.uniform(50.0, 2000.0), 2)))
            estimated_cost = labor_cost + material_cost
            
            # Random date within last 30 days or next 7 days
            if random.choice([True, False]):
                # Past booking
                date = datetime.utcnow() - timedelta(days=random.randint(1, 30))
            else:
                # Future booking
                date = datetime.utcnow() + timedelta(days=random.randint(1, 7))
            
            status = random.choice([
                BookingStatus.PENDING,
                BookingStatus.CONFIRMED,
                BookingStatus.IN_PROGRESS,
                BookingStatus.COMPLETED,
                BookingStatus.COMPLETED,  # Weight towards completed
                BookingStatus.CANCELLED,
            ])
            
            booking = Booking(
                client_id=client.id,
                artisan_id=artisan.id,
                service=f"[SEED] {service}",
                estimated_hours=estimated_hours,
                estimated_cost=estimated_cost,
                labor_cost=labor_cost,
                material_cost=material_cost,
                range_min=estimated_cost * Decimal("0.8"),
                range_max=estimated_cost * Decimal("1.2"),
                status=status,
                date=date,
                location=client.address.replace("[SEED] ", ""),
                notes=f"[SEED] Auto-generated booking for testing",
            )
            db.add(booking)
            bookings.append(booking)
        
        db.commit()
        print(f"✓ Created {len(bookings)} bookings")
        
        print("\n✅ Seed data created successfully!")
        print(f"\nSummary:")
        print(f"  - Artisans: {len(artisans)}")
        print(f"  - Clients: {len(clients)}")
        print(f"  - Bookings: {len(bookings)}")
        print(f"\nAll users have password: 'password123'")
        print(f"Artisan emails: artisan0.*@example.com, artisan1.*@example.com, etc.")
        print(f"Client emails: client0.*@example.com, client1.*@example.com, etc.")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("🌱 Starting database seeding...")
    seed_database()
