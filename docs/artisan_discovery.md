# Artisan Discovery: Nearby with Filters

This document describes the extended `/artisans/nearby` endpoint that enables clients to discover artisans not just by proximity, but also by skills, ratings, and availability. Results are paginated and sorted.

## Endpoint

- Method: `GET`
- Path: `/api/v1/artisans/nearby`

## Query Parameters

- `lat` (required, float)
  - Client latitude.
- `lon` (required, float)
  - Client longitude.
- `radius_km` (optional, float, default: `25.0`, range: `0..200`)
  - Search radius in kilometers.
- `skill` (optional, string)
  - Filter by skill keyword (e.g., `plumber`). Matches against `Artisan.specialties` text field via case-insensitive contains.
- `min_rating` (optional, float, `0..5`)
  - Minimum average rating filter.
- `available` (optional, boolean)
  - Filter by current availability (`true` or `false`).
- `page` (optional, int, default: `1`, min: `1`)
  - Page index (1-based).
- `page_size` (optional, int, default: `10`, range: `1..100`)
  - Number of results per page.

## Filtering and Sorting Logic

- Proximity is computed using the Haversine great-circle distance formula inside SQL (see `app/services/artisan_service.py::_distance_expr`).
- Optional filters are applied on top of proximity:
  - Skill: `Artisan.specialties ILIKE "%{skill}%"`.
  - Minimum rating: `Artisan.rating >= min_rating`.
  - Availability: `Artisan.is_available == available`.
  - Radius: `distance_km <= radius_km`.
- Sorting:
  - Primary: distance ascending (`nearest` first).
  - Secondary: rating descending.

## Pagination

- Default page size is `10` when `page_size` is not provided.
- `page` and `page_size` are validated and bounded (`1..100`).
- Response includes `total`, `page`, and `page_size` for client-side paging.

## Caching

- Redis-backed caching wraps the query via `find_nearby_artisans_cached()`.
- Cache key includes `lat`, `lon`, `radius`, `skill`, `min_rating`, `available`, `page`, `size`.
- Default TTL: `120` seconds.

## Response Schema

```json
{
  "items": [
    {
      "id": 1,
      "business_name": "Fix-It Plumbing Co.",
      "description": "Expert residential plumbing services.",
      "specialties": "[\"plumber\", \"pipe repair\"]",
      "experience_years": 8,
      "hourly_rate": 65.0,
      "location": "San Jose, CA",
      "latitude": 37.3382,
      "longitude": -121.8863,
      "is_verified": true,
      "is_available": true,
      "rating": 4.7,
      "total_reviews": 124,
      "distance_km": 3.42
    }
  ],
  "total": 27,
  "page": 1,
  "page_size": 10
}
```

## Example Requests

- Nearby, default pagination (10 per page):
```
GET /api/v1/artisans/nearby?lat=37.7749&lon=-122.4194
```

- Nearby + skill filter:
```
GET /api/v1/artisans/nearby?lat=37.7749&lon=-122.4194&skill=plumber
```

- Nearby + skill + min_rating:
```
GET /api/v1/artisans/nearby?lat=37.7749&lon=-122.4194&skill=plumber&min_rating=4
```

- Nearby + availability only:
```
GET /api/v1/artisans/nearby?lat=37.7749&lon=-122.4194&available=true
```

- Combined: nearby + skill + min_rating + availability with pagination:
```
GET /api/v1/artisans/nearby?lat=37.7749&lon=-122.4194&radius_km=15&skill=plumber&min_rating=4&available=true&page=2&page_size=10
```

## Implementation Pointers

- Service: `app/services/artisan_service.py`
  - `find_nearby_artisans()` builds the SQLAlchemy query and paginates.
  - `find_nearby_artisans_cached()` adds Redis caching.
- Endpoint: `app/api/v1/endpoints/artisan.py` → `GET /artisans/nearby`.
- Router registration: `app/api/v1/api.py` includes the `artisan` router.
- Models: `app/models/artisan.py` for fields used in filtering/sorting.

## Notes

- `Artisan.specialties` is stored as text; if later migrated to JSON, the skill filter can be updated to use JSON containment operators.
- Distance computation uses trig functions (requires database with trig support; tested with PostgreSQL).
