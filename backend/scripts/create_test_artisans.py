#!/usr/bin/env python3
"""
Script to create test artisan data for geolocation testing.
This script creates artisans with realistic locations across major cities.
"""

import asyncio
import random
import sys
import os
from typing import List, Dict, Any

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.db.database import get_db
from app.services.artisan import ArtisanService
from app.services.geolocation import geolocation_service
from app.schemas.artisan import ArtisanProfileCreate
from app.models.user import User, RoleEnum
from sqlalchemy.orm import Session

# Test data for major cities
TEST_LOCATIONS = [
    # New York City area
    {"city": "New York", "lat": 40.7128, "lng": -74.0060, "radius": 0.1},
    {"city": "Brooklyn", "lat": 40.6782, "lng": -73.9442, "radius": 0.05},
    {"city": "Queens", "lat": 40.7282, "lng": -73.7949, "radius": 0.05},
    
    # Los Angeles area
    {"city": "Los Angeles", "lat": 34.0522, "lng": -118.2437, "radius": 0.1},
    {"city": "Santa Monica", "lat": 34.0195, "lng": -118.4912, "radius": 0.03},
    {"city": "Beverly Hills", "lat": 34.0736, "lng": -118.4004, "radius": 0.02},
    
    # Chicago area
    {"city": "Chicago", "lat": 41.8781, "lng": -87.6298, "radius": 0.08},
    {"city": "Evanston", "lat": 42.0451, "lng": -87.6877, "radius": 0.03},
    
    # San Francisco area
    {"city": "San Francisco", "lat": 37.7749, "lng": -122.4194, "radius": 0.05},
    {"city": "Oakland", "lat": 37.8044, "lng": -122.2712, "radius": 0.04},
    
    # Other major cities
    {"city": "Boston", "lat": 42.3601, "lng": -71.0589, "radius": 0.06},
    {"city": "Seattle", "lat": 47.6062, "lng": -122.3321, "radius": 0.06},
    {"city": "Austin", "lat": 30.2672, "lng": -97.7431, "radius": 0.05},
    {"city": "Denver", "lat": 39.7392, "lng": -104.9903, "radius": 0.05},
    {"city": "Miami", "lat": 25.7617, "lng": -80.1918, "radius": 0.05},
]

# Artisan specialties
SPECIALTIES = [
    "pottery", "ceramics", "jewelry", "woodworking", "metalworking",
    "glassblowing", "textiles", "painting", "sculpture", "leatherwork",
    "basketry", "calligraphy", "printmaking", "photography", "weaving",
    "embroidery", "quilting", "blacksmithing", "silversmithing", "goldsmithing"
]

# Business name templates
BUSINESS_TEMPLATES = [
    "{specialty} Studio", "{city} {specialty}", "Artisan {specialty} Works",
    "{specialty} Creations", "The {specialty} Workshop", "{specialty} & Co.",
    "Handcrafted {specialty}", "{specialty} Artistry", "Creative {specialty}",
    "{specialty} Gallery", "Master {specialty}", "{specialty} Collective"
]

# Description templates
DESCRIPTION_TEMPLATES = [
    "Handcrafted {specialty} with traditional techniques and modern design.",
    "Custom {specialty} pieces created with passion and attention to detail.",
    "Artisan {specialty} studio specializing in unique, one-of-a-kind pieces.",
    "Traditional {specialty} craftsmanship meets contemporary artistic vision.",
    "Bespoke {specialty} creations for discerning clients and collectors.",
    "Award-winning {specialty} artist with over {years} years of experience.",
    "Sustainable {specialty} using eco-friendly materials and methods.",
    "Fine {specialty} inspired by {city} culture and artistic heritage."
]

def generate_random_location(base_location: Dict[str, Any]) -> Dict[str, float]:
    """Generate a random location within a radius of the base location."""
    lat_offset = random.uniform(-base_location["radius"], base_location["radius"])
    lng_offset = random.uniform(-base_location["radius"], base_location["radius"])
    
    return {
        "latitude": base_location["lat"] + lat_offset,
        "longitude": base_location["lng"] + lng_offset
    }

def generate_artisan_data(location_data: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Generate realistic artisan profile data."""
    specialty = random.choice(SPECIALTIES)
    city = location_data["city"]
    
    # Generate business name
    business_name = random.choice(BUSINESS_TEMPLATES).format(
        specialty=specialty.title(),
        city=city
    )
    
    # Generate description
    years = random.randint(3, 25)
    description = random.choice(DESCRIPTION_TEMPLATES).format(
        specialty=specialty,
        city=city,
        years=years
    )
    
    # Generate location
    coords = generate_random_location(location_data)
    
    # Generate address (simplified)
    street_num = random.randint(100, 9999)
    street_names = ["Main St", "Art Ave", "Creative Blvd", "Studio Dr", "Craft Ln", "Gallery Way"]
    address = f"{street_num} {random.choice(street_names)}, {city}"
    
    # Generate contact info
    phone = f"+1-{random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
    email = f"info@{business_name.lower().replace(' ', '').replace('&', 'and')}.com"
    website = f"https://{business_name.lower().replace(' ', '').replace('&', 'and')}.com"
    
    # Generate ratings
    rating = round(random.uniform(3.5, 5.0), 1)
    total_reviews = random.randint(5, 150)
    
    # Generate specialties (1-3 related specialties)
    artisan_specialties = [specialty]
    if random.random() > 0.6:  # 40% chance of additional specialty
        related_specialties = [s for s in SPECIALTIES if s != specialty]
        artisan_specialties.append(random.choice(related_specialties))
    if random.random() > 0.8:  # 20% chance of third specialty
        remaining_specialties = [s for s in SPECIALTIES if s not in artisan_specialties]
        if remaining_specialties:
            artisan_specialties.append(random.choice(remaining_specialties))
    
    return {
        "business_name": business_name,
        "description": description,
        "specialties": artisan_specialties,
        "location": address,
        "latitude": coords["latitude"],
        "longitude": coords["longitude"],
        "phone": phone,
        "email": email,
        "website": website,
        "rating": rating,
        "total_reviews": total_reviews,
        "is_available": random.choice([True, True, True, False])  # 75% available
    }

async def create_test_user(db: Session, email: str, index: int) -> User:
    """Create a test user for the artisan."""
    from app.models.user import User
    from app.core.security import get_password_hash
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return existing_user
    
    user = User(
        email=email,
        hashed_password=get_password_hash("testpassword123"),
        role=RoleEnum.ARTISAN,
        full_name=f"Test Artisan {index}",
        username=f"testartisan{index}",
        is_active=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

async def create_test_artisans(count: int = 100):
    """Create test artisans with realistic location data."""
    print(f"Creating {count} test artisans...")
    
    db = next(get_db())
    service = ArtisanService(db)
    
    created_count = 0
    errors = []
    
    try:
        for i in range(count):
            try:
                # Select random location
                location_data = random.choice(TEST_LOCATIONS)
                
                # Generate artisan data
                artisan_data = generate_artisan_data(location_data, i + 1)
                
                # Create test user
                user = await create_test_user(db, artisan_data["email"], i + 1)
                
                # Create artisan profile
                profile_data = ArtisanProfileCreate(**artisan_data)
                artisan = await service.create_artisan_profile(user.id, profile_data)
                
                if artisan:
                    created_count += 1
                    if created_count % 10 == 0:
                        print(f"Created {created_count}/{count} artisans...")
                else:
                    errors.append(f"Failed to create artisan {i + 1}")
                    
            except Exception as e:
                errors.append(f"Error creating artisan {i + 1}: {str(e)}")
                continue
    
    finally:
        db.close()
    
    print(f"\nCompleted! Created {created_count} artisans.")
    if errors:
        print(f"Errors encountered: {len(errors)}")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  - {error}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more errors")
    
    # Test Redis sync
    print("\nSyncing locations to Redis...")
    try:
        await service.sync_locations_to_redis()
        print("Redis sync completed successfully!")
    except Exception as e:
        print(f"Redis sync failed: {e}")
    
    return created_count

async def test_nearby_search():
    """Test the nearby search functionality."""
    print("\nTesting nearby search functionality...")
    
    db = next(get_db())
    service = ArtisanService(db)
    
    # Test searches in different cities
    test_searches = [
        {"name": "NYC", "lat": 40.7128, "lng": -74.0060, "radius": 10},
        {"name": "LA", "lat": 34.0522, "lng": -118.2437, "radius": 15},
        {"name": "Chicago", "lat": 41.8781, "lng": -87.6298, "radius": 12},
    ]
    
    for search in test_searches:
        try:
            from app.schemas.artisan import NearbyArtisansRequest
            
            request = NearbyArtisansRequest(
                latitude=search["lat"],
                longitude=search["lng"],
                radius_km=search["radius"],
                limit=10
            )
            
            result = await service.find_nearby_artisans(request)
            print(f"{search['name']}: Found {len(result.artisans)} artisans within {search['radius']}km")
            
            if result.artisans:
                closest = result.artisans[0]
                print(f"  Closest: {closest.business_name} ({closest.distance_km:.1f}km)")
                
        except Exception as e:
            print(f"Error testing {search['name']}: {e}")
    
    db.close()

def main():
    """Main function to run the test data creation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Create test artisan data")
    parser.add_argument("--count", type=int, default=100, help="Number of artisans to create")
    parser.add_argument("--test-search", action="store_true", help="Test nearby search after creation")
    
    args = parser.parse_args()
    
    # Run the async function
    loop = asyncio.get_event_loop()
    
    try:
        created_count = loop.run_until_complete(create_test_artisans(args.count))
        
        if args.test_search and created_count > 0:
            loop.run_until_complete(test_nearby_search())
            
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        loop.close()

if __name__ == "__main__":
    main()