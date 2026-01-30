import math
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.artisan import ArtisanProfileCreate, NearbyArtisansRequest
from app.services.artisan import ArtisanService


# Mock Redis Logic for Geospatial Operations
class MockRedisGeo:
    def __init__(self):
        self.geo_data = {}  # Format: {key: {member: (lon, lat)}}
        self.hashes = {}    # Format: {key: value}

    async def geoadd(self, key, lon, lat, member):
        if key not in self.geo_data:
            self.geo_data[key] = {}
        self.geo_data[key][str(member)] = (float(lon), float(lat))
        return 1

    async def hset(self, name, mapping=None):
        self.hashes[name] = mapping
        return 1

    async def delete(self, *names):
        for name in names:
            if name in self.hashes:
                del self.hashes[name]
        return 1

    async def zrem(self, key, member):
        if key in self.geo_data and str(member) in self.geo_data[key]:
            del self.geo_data[key][str(member)]
            return 1
        return 0

    async def georadius(self, key, lon, lat, radius, unit='m', withdist=False, withcoord=False, sort='ASC', count=None):
        if key not in self.geo_data:
            return []

        center_lon = float(lon)
        center_lat = float(lat)
        radius_m = float(radius)
        if unit == 'km':
            radius_m *= 1000

        results = []

        for member, coords in self.geo_data[key].items():
            member_lon, member_lat = coords

            # Simplified Haversine for the mock
            # We can use the service's static method if available, or just implement it
            dist_m = self._calculate_distance_m(center_lat, center_lon, member_lat, member_lon)

            if dist_m <= radius_m:
                result_item = [member.encode('utf-8')] # Redis returns bytes usually, but let's check service usage
                # The service expects: result[0]=id, result[1]=dist, result[2]=coords
                if withdist:
                    result_item.append(dist_m)
                if withcoord:
                    result_item.append((member_lon, member_lat))

                results.append(result_item)

        # Sort
        results.sort(key=lambda x: x[1] if withdist else 0)

        if count:
            results = results[:count]

        return results

    def _calculate_distance_m(self, lat1, lon1, lat2, lon2):
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c


@pytest.fixture
def mock_redis():
    mock_geo = MockRedisGeo()

    # Create an AsyncMock that delegates relevant calls to our MockRedisGeo
    mock = AsyncMock()
    mock.geoadd.side_effect = mock_geo.geoadd
    mock.georadius.side_effect = mock_geo.georadius
    mock.hset.side_effect = mock_geo.hset
    mock.delete.side_effect = mock_geo.delete
    mock.zrem.side_effect = mock_geo.zrem

    return mock

@pytest.mark.asyncio
async def test_geolocation_search_filtering(db_session, mock_redis):
    """
    Test that find_nearby_artisans correctly filters artisans based on radius.

    Setup:
    - Artisan A at (40.0, -74.0) -> Search Center
    - Artisan B at (41.0, -74.0) -> ~111 km away

    Action:
    - Search with radius 50km

    Assertion:
    - Artisan A is included
    - Artisan B is excluded
    """

    # Patch the cache.redis in the geolocation service
    with patch("app.core.cache.cache.redis", mock_redis):

        service = ArtisanService(db_session)

        # 1. Create Users
        user_a = User(
            email="artisan_a@test.com",
            hashed_password=get_password_hash("pass"),
            role="artisan",
            full_name="Artisan A"
        )
        user_b = User(
            email="artisan_b@test.com",
            hashed_password=get_password_hash("pass"),
            role="artisan",
            full_name="Artisan B"
        )
        db_session.add(user_a)
        db_session.add(user_b)
        db_session.commit()
        db_session.refresh(user_a)
        db_session.refresh(user_b)

        # 2. Create Artisan Profiles
        # Artisan A: At the search center (Lat 40.0, Lon -74.0)
        profile_a = ArtisanProfileCreate(
            business_name="Artisan A Business",
            description="Near center",
            specialties=["plumbing"],
            experience_years=5,
            hourly_rate=Decimal("50.00"),
            location="Center City",
            latitude=Decimal("40.0"),
            longitude=Decimal("-74.0")
        )

        # Artisan B: ~111km away (Lat 41.0, Lon -74.0)
        profile_b = ArtisanProfileCreate(
            business_name="Artisan B Business",
            description="Far away",
            specialties=["electrical"],
            experience_years=5,
            hourly_rate=Decimal("50.00"),
            location="Far City",
            latitude=Decimal("41.0"),
            longitude=Decimal("-74.0")
        )

        # Creating profiles triggers add_artisan_location which uses our mock_redis
        artisan_a = await service.create_artisan_profile(user_a.id, profile_a)
        artisan_b = await service.create_artisan_profile(user_b.id, profile_b)

        assert artisan_a is not None
        assert artisan_b is not None

        # 3. Execute Search
        # Center: (40.0, -74.0), Radius: 50 km
        search_request = NearbyArtisansRequest(
            latitude=Decimal("40.0"),
            longitude=Decimal("-74.0"),
            radius_km=50.0,
            limit=10,
            specialties=None,
            min_rating=None,
            is_available=None
        )

        response = await service.find_nearby_artisans(search_request)

        # 4. Assertions
        found_artisans = response["artisans"]
        found_ids = [a["id"] for a in found_artisans]

        print(f"Found Artisans: {found_artisans}")

        # Assertion 1: Artisan A should be in the results (Distance ~0)
        assert artisan_a.id in found_ids, "Artisan A (0km) should be found"

        # Assertion 2: Artisan B should NOT be in the results (Distance ~111km > 50km)
        assert artisan_b.id not in found_ids, "Artisan B (~111km) should strictly be excluded from 50km search"

        # Verify specific distance logic
        artisan_a_result = next(a for a in found_artisans if a["id"] == artisan_a.id)
        assert artisan_a_result["distance_km"] < 1.0, "Artisan A distance should be negligible"

        # Additional Sanity Check: Ensure B is excluded even at max radius (100km)
        # Artisan B is ~111km away, so it should still be excluded
        max_search_request = NearbyArtisansRequest(
            latitude=Decimal("40.0"),
            longitude=Decimal("-74.0"),
            radius_km=100.0,
            limit=10
        )
        max_response = await service.find_nearby_artisans(max_search_request)
        max_found_ids = [a["id"] for a in max_response["artisans"]]

        assert artisan_b.id not in max_found_ids, "Artisan B (~111km) should be excluded even at max radius (100km)"
