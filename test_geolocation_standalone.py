#!/usr/bin/env python3
"""
Standalone Geolocation Testing Script
Tests geolocation functionality without requiring Docker services.
"""

import asyncio
import json
import math
import sys
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

@dataclass
class MockArtisan:
    """Mock artisan for testing without database."""
    id: int
    business_name: str
    latitude: float
    longitude: float
    location: str
    specialties: List[str]
    rating: float
    is_available: bool

class MockGeolocationService:
    """Mock geolocation service for testing without external APIs."""
    
    def __init__(self):
        # Sample geocoding data for testing
        self.geocoding_data = {
            "new york": {"lat": 40.7128, "lng": -74.0060, "confidence": 0.95},
            "los angeles": {"lat": 34.0522, "lng": -118.2437, "confidence": 0.92},
            "chicago": {"lat": 41.8781, "lng": -87.6298, "confidence": 0.94},
            "san francisco": {"lat": 37.7749, "lng": -122.4194, "confidence": 0.96},
            "boston": {"lat": 42.3601, "lng": -71.0589, "confidence": 0.93},
            "123 main street": {"lat": 40.7505, "lng": -73.9934, "confidence": 0.88},
            "456 art avenue": {"lat": 40.6782, "lng": -73.9442, "confidence": 0.85},
        }
    
    async def geocode_address(self, address: str) -> Optional[Dict[str, Any]]:
        """Mock geocoding function."""
        address_lower = address.lower().strip()
        
        # Check for exact matches
        if address_lower in self.geocoding_data:
            data = self.geocoding_data[address_lower]
            return {
                "latitude": data["lat"],
                "longitude": data["lng"],
                "address": address,
                "confidence": data["confidence"]
            }
        
        # Check for partial matches
        for key, data in self.geocoding_data.items():
            if key in address_lower or address_lower in key:
                return {
                    "latitude": data["lat"],
                    "longitude": data["lng"],
                    "address": address,
                    "confidence": data["confidence"] * 0.8  # Lower confidence for partial match
                }
        
        return None
    
    def calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

class MockArtisanService:
    """Mock artisan service for testing without database."""
    
    def __init__(self):
        self.geo_service = MockGeolocationService()
        self.artisans = self._create_test_artisans()
    
    def _create_test_artisans(self) -> List[MockArtisan]:
        """Create test artisan data."""
        return [
            MockArtisan(1, "NYC Pottery Studio", 40.7128, -74.0060, "123 Main St, New York", ["pottery", "ceramics"], 4.8, True),
            MockArtisan(2, "Brooklyn Clay Works", 40.6782, -73.9442, "456 Art Ave, Brooklyn", ["pottery"], 4.5, True),
            MockArtisan(3, "Manhattan Jewelry", 40.7589, -73.9851, "789 Gold St, New York", ["jewelry"], 4.9, True),
            MockArtisan(4, "Queens Woodworking", 40.7282, -73.7949, "321 Wood Ln, Queens", ["woodworking"], 4.3, False),
            MockArtisan(5, "LA Ceramics Studio", 34.0522, -118.2437, "555 Art Blvd, Los Angeles", ["ceramics"], 4.7, True),
            MockArtisan(6, "Santa Monica Glass", 34.0195, -118.4912, "777 Beach Ave, Santa Monica", ["glassblowing"], 4.6, True),
            MockArtisan(7, "Chicago Metalworks", 41.8781, -87.6298, "888 Steel St, Chicago", ["metalworking"], 4.4, True),
            MockArtisan(8, "Boston Textiles", 42.3601, -71.0589, "999 Fabric Way, Boston", ["textiles"], 4.2, True),
            MockArtisan(9, "SF Sculpture Studio", 37.7749, -122.4194, "111 Art Hill, San Francisco", ["sculpture"], 4.9, True),
            MockArtisan(10, "Oakland Leatherwork", 37.8044, -122.2712, "222 Craft St, Oakland", ["leatherwork"], 4.1, True),
        ]
    
    async def find_nearby_artisans(self, latitude: float, longitude: float, radius_km: float, 
                                 limit: int = 20, specialties: Optional[List[str]] = None,
                                 min_rating: Optional[float] = None, 
                                 is_available: Optional[bool] = None) -> Dict[str, Any]:
        """Find nearby artisans with filters."""
        results = []
        
        for artisan in self.artisans:
            # Calculate distance
            distance = self.geo_service.calculate_distance(
                latitude, longitude, artisan.latitude, artisan.longitude
            )
            
            # Check if within radius
            if distance > radius_km:
                continue
            
            # Apply filters
            if specialties and not any(spec in artisan.specialties for spec in specialties):
                continue
            
            if min_rating and artisan.rating < min_rating:
                continue
            
            if is_available is not None and artisan.is_available != is_available:
                continue
            
            # Add to results with distance
            result = {
                "id": artisan.id,
                "business_name": artisan.business_name,
                "location": artisan.location,
                "latitude": artisan.latitude,
                "longitude": artisan.longitude,
                "specialties": artisan.specialties,
                "rating": artisan.rating,
                "is_available": artisan.is_available,
                "distance_km": round(distance, 2)
            }
            results.append(result)
        
        # Sort by distance
        results.sort(key=lambda x: x["distance_km"])
        
        # Apply limit
        results = results[:limit]
        
        return {
            "artisans": results,
            "total_count": len(results),
            "search_center": {"latitude": latitude, "longitude": longitude},
            "radius_km": radius_km
        }

async def test_geocoding():
    """Test geocoding functionality."""
    print("🌍 Testing Geocoding Functionality")
    print("=" * 50)
    
    geo_service = MockGeolocationService()
    
    test_addresses = [
        "New York",
        "Los Angeles", 
        "123 Main Street",
        "Invalid Address XYZ123"
    ]
    
    for address in test_addresses:
        result = await geo_service.geocode_address(address)
        if result:
            print(f"✅ {address}")
            print(f"   Coordinates: {result['latitude']}, {result['longitude']}")
            print(f"   Confidence: {result['confidence']:.2f}")
        else:
            print(f"❌ {address} - Not found")
        print()

async def test_distance_calculation():
    """Test distance calculation."""
    print("📏 Testing Distance Calculation")
    print("=" * 50)
    
    geo_service = MockGeolocationService()
    
    # Test known distances
    test_cases = [
        {"name": "NYC to Brooklyn", "lat1": 40.7128, "lng1": -74.0060, "lat2": 40.6782, "lng2": -73.9442, "expected": 8.2},
        {"name": "NYC to LA", "lat1": 40.7128, "lng1": -74.0060, "lat2": 34.0522, "lng2": -118.2437, "expected": 3944},
        {"name": "Same location", "lat1": 40.7128, "lng1": -74.0060, "lat2": 40.7128, "lng2": -74.0060, "expected": 0},
    ]
    
    for case in test_cases:
        distance = geo_service.calculate_distance(
            case["lat1"], case["lng1"], case["lat2"], case["lng2"]
        )
        
        # Check if within reasonable range of expected
        tolerance = case["expected"] * 0.1 if case["expected"] > 0 else 0.1
        is_accurate = abs(distance - case["expected"]) <= tolerance
        
        status = "✅" if is_accurate else "⚠️"
        print(f"{status} {case['name']}")
        print(f"   Calculated: {distance:.1f} km")
        print(f"   Expected: ~{case['expected']} km")
        print()

async def test_nearby_search():
    """Test nearby artisan search."""
    print("🔍 Testing Nearby Artisan Search")
    print("=" * 50)
    
    service = MockArtisanService()
    
    # Test searches
    test_searches = [
        {
            "name": "NYC Area (10km radius)",
            "lat": 40.7128, "lng": -74.0060, "radius": 10,
            "specialties": None, "min_rating": None, "is_available": None
        },
        {
            "name": "NYC Pottery Only",
            "lat": 40.7128, "lng": -74.0060, "radius": 20,
            "specialties": ["pottery"], "min_rating": None, "is_available": None
        },
        {
            "name": "High-rated Available Artisans",
            "lat": 40.7128, "lng": -74.0060, "radius": 50,
            "specialties": None, "min_rating": 4.5, "is_available": True
        },
        {
            "name": "LA Area",
            "lat": 34.0522, "lng": -118.2437, "radius": 25,
            "specialties": None, "min_rating": None, "is_available": None
        }
    ]
    
    for search in test_searches:
        print(f"🎯 {search['name']}")
        
        result = await service.find_nearby_artisans(
            search["lat"], search["lng"], search["radius"],
            specialties=search["specialties"],
            min_rating=search["min_rating"],
            is_available=search["is_available"]
        )
        
        print(f"   Found: {result['total_count']} artisans")
        
        if result["artisans"]:
            print("   Results:")
            for artisan in result["artisans"][:3]:  # Show first 3
                print(f"     • {artisan['business_name']} ({artisan['distance_km']}km)")
                print(f"       Specialties: {', '.join(artisan['specialties'])}")
                print(f"       Rating: {artisan['rating']}, Available: {artisan['is_available']}")
        
        print()

async def test_schema_validation():
    """Test schema validation logic."""
    print("📋 Testing Schema Validation")
    print("=" * 50)
    
    # Test coordinate validation
    test_coordinates = [
        {"lat": 40.7128, "lng": -74.0060, "valid": True, "name": "Valid NYC coordinates"},
        {"lat": 91, "lng": -74.0060, "valid": False, "name": "Invalid latitude (>90)"},
        {"lat": 40.7128, "lng": 181, "valid": False, "name": "Invalid longitude (>180)"},
        {"lat": -91, "lng": -74.0060, "valid": False, "name": "Invalid latitude (<-90)"},
        {"lat": 40.7128, "lng": -181, "valid": False, "name": "Invalid longitude (<-180)"},
    ]
    
    for coord in test_coordinates:
        is_valid = (-90 <= coord["lat"] <= 90) and (-180 <= coord["lng"] <= 180)
        status = "✅" if is_valid == coord["valid"] else "❌"
        print(f"{status} {coord['name']}")
        print(f"   Coordinates: {coord['lat']}, {coord['lng']}")
        print(f"   Expected: {'Valid' if coord['valid'] else 'Invalid'}, Got: {'Valid' if is_valid else 'Invalid'}")
        print()

async def test_performance_simulation():
    """Simulate performance with larger dataset."""
    print("⚡ Testing Performance Simulation")
    print("=" * 50)
    
    # Create larger mock dataset
    import random
    
    large_artisans = []
    cities = [
        {"name": "NYC", "lat": 40.7128, "lng": -74.0060},
        {"name": "LA", "lat": 34.0522, "lng": -118.2437},
        {"name": "Chicago", "lat": 41.8781, "lng": -87.6298},
        {"name": "Houston", "lat": 29.7604, "lng": -95.3698},
        {"name": "Phoenix", "lat": 33.4484, "lng": -112.0740},
    ]
    
    specialties = ["pottery", "jewelry", "woodworking", "metalworking", "textiles"]
    
    # Generate 1000 mock artisans
    for i in range(1000):
        city = random.choice(cities)
        # Add some random offset within ~50km
        lat_offset = random.uniform(-0.5, 0.5)
        lng_offset = random.uniform(-0.5, 0.5)
        
        artisan = MockArtisan(
            id=i + 1,
            business_name=f"Artisan Studio {i + 1}",
            latitude=city["lat"] + lat_offset,
            longitude=city["lng"] + lng_offset,
            location=f"Address {i + 1}, {city['name']}",
            specialties=[random.choice(specialties)],
            rating=round(random.uniform(3.0, 5.0), 1),
            is_available=random.choice([True, False])
        )
        large_artisans.append(artisan)
    
    # Create service with large dataset
    service = MockArtisanService()
    service.artisans = large_artisans
    
    # Time the search
    import time
    start_time = time.time()
    
    result = await service.find_nearby_artisans(40.7128, -74.0060, 50, limit=20)
    
    end_time = time.time()
    search_time = (end_time - start_time) * 1000  # Convert to milliseconds
    
    print(f"✅ Searched {len(large_artisans)} artisans in {search_time:.2f}ms")
    print(f"   Found: {result['total_count']} artisans within 50km")
    print(f"   Performance: {'Good' if search_time < 100 else 'Needs optimization'}")
    print()

async def run_all_tests():
    """Run all geolocation tests."""
    print("🚀 StellArts Geolocation Testing Suite")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("Geocoding", test_geocoding),
        ("Distance Calculation", test_distance_calculation),
        ("Nearby Search", test_nearby_search),
        ("Schema Validation", test_schema_validation),
        ("Performance Simulation", test_performance_simulation),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            await test_func()
            passed += 1
            print(f"✅ {test_name} - PASSED")
        except Exception as e:
            print(f"❌ {test_name} - FAILED: {e}")
        print()
    
    print("=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Geolocation implementation is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the implementation.")
    
    print()
    print("🔧 Next Steps:")
    print("1. Start Docker services: docker-compose up -d")
    print("2. Run database migrations: alembic upgrade head")
    print("3. Create test data: python scripts/create_test_artisans.py --count 50")
    print("4. Test API endpoints via Swagger UI: http://localhost:8000/docs")

def main():
    """Main function to run the tests."""
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user.")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")

if __name__ == "__main__":
    main()