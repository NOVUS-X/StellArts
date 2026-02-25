# Artisan Geolocation Documentation

## Overview

This document describes the geolocation feature implementation for the StellArts platform, enabling clients to discover nearby artisans efficiently using Redis geospatial queries.

## Schema Changes

### Database Model Updates

The `Artisan` model in `app/models/artisan.py` includes geolocation fields:

```python
class Artisan(Base):
    __tablename__ = "artisans"
    
    # ... existing fields ...
    latitude = Column(DECIMAL(10, 8), nullable=True)    # -90.00000000 to 90.00000000
    longitude = Column(DECIMAL(11, 8), nullable=True)   # -180.00000000 to 180.00000000
    location = Column(String(255), nullable=True)       # Human-readable address
```

### Pydantic Schemas

New schemas in `app/schemas/artisan.py`:

#### Location Update Schema
```python
class ArtisanLocationUpdate(BaseModel):
    location: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
```

#### Nearby Search Schemas
```python
class NearbyArtisansRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(10.0, gt=0, le=100)
    limit: int = Field(20, gt=0, le=100)
    specialties: Optional[List[str]] = None
    min_rating: Optional[float] = Field(None, ge=0, le=5)

class ArtisanWithDistance(ArtisanOut):
    distance_km: float = Field(..., description="Distance in kilometers")

class NearbyArtisansResponse(BaseModel):
    artisans: List[ArtisanWithDistance]
    total_count: int
    search_center: Dict[str, float]
    radius_km: float
```

#### Geocoding Schemas
```python
class GeolocationRequest(BaseModel):
    address: str = Field(..., min_length=5, max_length=500)

class GeolocationResponse(BaseModel):
    latitude: float
    longitude: float
    address: str
    confidence: float = Field(..., ge=0, le=1)
```

## API Endpoints

### 1. Find Nearby Artisans

**Endpoint:** `POST /api/v1/artisans/nearby`

**Description:** Find artisans within a specified radius of given coordinates.

**Request Body:**
```json
{
    "latitude": 40.7128,
    "longitude": -74.0060,
    "radius_km": 10.0,
    "limit": 20,
    "specialties": ["pottery", "jewelry"],
    "min_rating": 4.0
}
```

**Response:**
```json
{
    "artisans": [
        {
            "id": 1,
            "user_id": 123,
            "business_name": "Clay Creations Studio",
            "description": "Handcrafted pottery and ceramics",
            "specialties": ["pottery", "ceramics"],
            "location": "123 Art Street, New York, NY",
            "latitude": 40.7589,
            "longitude": -73.9851,
            "phone": "+1-555-0123",
            "email": "info@claycreations.com",
            "website": "https://claycreations.com",
            "rating": 4.8,
            "total_reviews": 42,
            "is_available": true,
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-20T14:45:00Z",
            "distance_km": 2.3
        }
    ],
    "total_count": 1,
    "search_center": {
        "latitude": 40.7128,
        "longitude": -74.0060
    },
    "radius_km": 10.0
}
```

### 2. Geocode Address

**Endpoint:** `POST /api/v1/artisans/geocode`

**Description:** Convert an address to latitude/longitude coordinates.

**Authentication:** Required (any authenticated user)

**Request Body:**
```json
{
    "address": "123 Main Street, New York, NY 10001"
}
```

**Response:**
```json
{
    "latitude": 40.7505,
    "longitude": -73.9934,
    "address": "123 Main Street, New York, NY 10001, United States",
    "confidence": 0.95
}
```

### 3. Update Artisan Location

**Endpoint:** `PUT /api/v1/artisans/location`

**Description:** Update artisan's location with optional automatic geocoding.

**Authentication:** Required (artisan role only)

**Request Body (with coordinates):**
```json
{
    "location": "456 Art Avenue, Brooklyn, NY",
    "latitude": 40.6782,
    "longitude": -73.9442
}
```

**Request Body (address only - will be geocoded):**
```json
{
    "location": "456 Art Avenue, Brooklyn, NY"
}
```

**Response:**
```json
{
    "id": 1,
    "user_id": 123,
    "business_name": "Clay Creations Studio",
    "location": "456 Art Avenue, Brooklyn, NY",
    "latitude": 40.6782,
    "longitude": -73.9442,
    // ... other artisan fields
}
```

### 4. List Artisans with Filters

**Endpoint:** `GET /api/v1/artisans/`

**Description:** List artisans with optional geolocation filters.

**Query Parameters:**
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 20, max: 100)
- `specialties`: Filter by specialties (comma-separated)
- `min_rating`: Minimum rating filter
- `is_available`: Filter by availability status
- `has_location`: Filter artisans with/without location data

**Example:**
```
GET /api/v1/artisans/?has_location=true&min_rating=4.0&limit=10
```

## Redis Geospatial Implementation

### Redis Key Structure

- **Geospatial Index:** `artisans:locations`
- **Location Data:** `artisan:location:{artisan_id}`

### Redis Operations

#### Adding Artisan Location
```python
# Add artisan to geospatial index
redis_client.geoadd(
    "artisans:locations",
    longitude, latitude, f"artisan:{artisan_id}"
)

# Store additional location metadata
redis_client.hset(
    f"artisan:location:{artisan_id}",
    mapping={
        "latitude": str(latitude),
        "longitude": str(longitude),
        "location": location,
        "updated_at": datetime.utcnow().isoformat()
    }
)
```

#### Finding Nearby Artisans
```python
# Search within radius using GEOSEARCH (Redis 6.2+)
nearby_results = redis_client.geosearch(
    name="artisans:locations",
    longitude=longitude,
    latitude=latitude,
    radius=radius_km,
    unit="km",
    withdist=True,
    withcoord=True,
    sort="ASC",
    count=limit
)
```

**Note:** The `GEOSEARCH` command replaced the deprecated `GEORADIUS` command in Redis 6.2. `GEORADIUS` was removed in Redis 7.0+.

#### Removing Artisan Location
```python
# Remove from geospatial index
redis_client.zrem("artisans:locations", f"artisan:{artisan_id}")

# Remove location metadata
redis_client.delete(f"artisan:location:{artisan_id}")
```

### Performance Optimization

1. **Geospatial Indexing:** Redis GEOSEARCH provides O(N+log(M)) complexity
2. **Caching:** Location data cached in Redis for fast retrieval
3. **Batch Operations:** Sync operations handle multiple artisans efficiently
4. **TTL Management:** Location cache with appropriate expiration

## Service Layer Architecture

### GeolocationService

Located in `app/services/geolocation.py`:

**Key Methods:**
- `geocode_address()`: Convert address to coordinates using OpenStreetMap
- `reverse_geocode()`: Convert coordinates to address
- `add_artisan_location()`: Add artisan to Redis geospatial index
- `remove_artisan_location()`: Remove artisan from Redis index
- `find_nearby_artisans()`: Query nearby artisans with distance
- `calculate_distance()`: Calculate distance between two points

### ArtisanService

Located in `app/services/artisan.py`:

**Key Methods:**
- `create_artisan_profile()`: Create profile with location sync to Redis
- `update_artisan_profile()`: Update profile with location sync
- `find_nearby_artisans()`: Find nearby artisans with database integration
- `geocode_and_update_location()`: Geocode address and update location
- `sync_locations_to_redis()`: Bulk sync database locations to Redis

## Testing and Validation

### Test Data Creation

Use the following script to create test artisans with locations:

```python
# Create test artisans in major cities
test_locations = [
    {"name": "NYC Pottery", "lat": 40.7128, "lng": -74.0060, "city": "New York"},
    {"name": "LA Ceramics", "lat": 34.0522, "lng": -118.2437, "city": "Los Angeles"},
    {"name": "Chicago Arts", "lat": 41.8781, "lng": -87.6298, "city": "Chicago"},
    # Add more test data...
]
```

### Performance Testing

Test with >100 artisans:

```bash
# Create 100+ test artisans
python scripts/create_test_artisans.py --count 150

# Test nearby search performance
curl -X POST "http://localhost:8000/api/v1/artisans/nearby" \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 40.7128,
    "longitude": -74.0060,
    "radius_km": 50,
    "limit": 50
  }'
```

### Validation Criteria

✅ **Coordinate Validation:**
- Latitude: -90 to 90 degrees
- Longitude: -180 to 180 degrees
- Address geocoding accuracy > 90%

✅ **Distance Calculations:**
- Haversine formula for accurate distance
- Results ordered by distance (ascending)
- Distance precision to 2 decimal places

✅ **Redis Performance:**
- Query response time < 100ms for 1000+ artisans
- Geospatial index memory usage optimized
- Automatic cleanup of stale location data

## Error Handling

### Common Error Scenarios

1. **Invalid Coordinates:**
   ```json
   {
     "detail": "Latitude must be between -90 and 90 degrees"
   }
   ```

2. **Geocoding Failure:**
   ```json
   {
     "detail": "Address not found or geocoding failed"
   }
   ```

3. **Redis Connection Error:**
   ```json
   {
     "detail": "Location service temporarily unavailable"
   }
   ```

4. **No Artisans Found:**
   ```json
   {
     "artisans": [],
     "total_count": 0,
     "search_center": {"latitude": 40.7128, "longitude": -74.0060},
     "radius_km": 10.0
   }
   ```

## Configuration

### Environment Variables

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Geolocation Service
NOMINATIM_USER_AGENT=StellArts/1.0
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org

# Rate Limiting
GEOCODING_RATE_LIMIT=60  # requests per minute
```

### Redis Configuration

```redis
# Recommended Redis settings for geospatial operations
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

## Monitoring and Maintenance

### Key Metrics

- **Geocoding Success Rate:** Target > 95%
- **Query Response Time:** Target < 100ms
- **Redis Memory Usage:** Monitor geospatial index size
- **API Usage:** Track nearby search frequency

### Maintenance Tasks

1. **Daily:** Sync database locations to Redis
2. **Weekly:** Clean up stale location cache entries
3. **Monthly:** Validate coordinate accuracy and update if needed

## Future Enhancements

1. **Advanced Filtering:** Add filters for business hours, services offered
2. **Caching Strategy:** Implement query result caching for popular locations
3. **Geofencing:** Add support for custom geographic boundaries
4. **Real-time Updates:** WebSocket notifications for location changes
5. **Analytics:** Track popular search areas and optimize accordingly

## Troubleshooting

### Common Issues

1. **Slow Queries:** Check Redis memory and consider increasing `maxmemory`
2. **Geocoding Failures:** Verify OpenStreetMap API availability
3. **Coordinate Drift:** Validate input data and implement bounds checking
4. **Memory Usage:** Monitor Redis geospatial index size and implement cleanup

### Debug Commands

```bash
# Check Redis geospatial data
redis-cli ZRANGE artisans:locations 0 -1 WITHSCORES

# Test geocoding service
curl "https://nominatim.openstreetmap.org/search?q=New+York&format=json"

# Monitor Redis memory
redis-cli INFO memory
```