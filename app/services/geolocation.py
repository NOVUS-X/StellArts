import asyncio
import aiohttp
import redis.asyncio as redis
from typing import Optional, List, Dict, Tuple
from decimal import Decimal
import json
import math
from urllib.parse import quote

from app.core.config import settings
from app.core.cache import cache
from app.schemas.artisan import GeolocationResponse, ArtisanWithDistance

class GeolocationService:
    """Service for handling geolocation operations and Redis geospatial indexing"""
    
    def __init__(self):
        self.redis_key = "artisan_locations"
        
    async def geocode_address(self, address: str) -> Optional[GeolocationResponse]:
        """
        Convert address to coordinates using OpenStreetMap Nominatim API
        (Free alternative to Google Maps API)
        """
        try:
            encoded_address = quote(address)
            url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_address}&limit=1"
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Stellarts/1.0 (contact@stellarts.com)'  # Required by Nominatim
                }
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            result = data[0]
                            return GeolocationResponse(
                                latitude=Decimal(str(result['lat'])),
                                longitude=Decimal(str(result['lon'])),
                                formatted_address=result.get('display_name', address),
                                confidence=float(result.get('importance', 0.5))
                            )
            return None
        except Exception as e:
            print(f"Geocoding error: {e}")
            return None
    
    async def reverse_geocode(self, latitude: Decimal, longitude: Decimal) -> Optional[str]:
        """Convert coordinates to address"""
        try:
            url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}"
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Stellarts/1.0 (contact@stellarts.com)'
                }
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('display_name')
            return None
        except Exception as e:
            print(f"Reverse geocoding error: {e}")
            return None
    
    async def add_artisan_location(self, artisan_id: int, latitude: Decimal, longitude: Decimal) -> bool:
        """Add or update artisan location in Redis geospatial index"""
        try:
            if not cache.redis:
                return False
                
            # Add to Redis geospatial index
            await cache.redis.geoadd(
                self.redis_key,
                float(longitude), float(latitude), str(artisan_id)
            )
            
            # Store additional artisan data
            artisan_data = {
                'latitude': str(latitude),
                'longitude': str(longitude),
                'updated_at': str(asyncio.get_event_loop().time())
            }
            await cache.redis.hset(
                f"artisan_geo:{artisan_id}",
                mapping=artisan_data
            )
            
            return True
        except Exception as e:
            print(f"Error adding artisan location to Redis: {e}")
            return False
    
    async def remove_artisan_location(self, artisan_id: int) -> bool:
        """Remove artisan from geospatial index"""
        try:
            if not cache.redis:
                return False
                
            # Remove from geospatial index
            await cache.redis.zrem(self.redis_key, str(artisan_id))
            
            # Remove additional data
            await cache.redis.delete(f"artisan_geo:{artisan_id}")
            
            return True
        except Exception as e:
            print(f"Error removing artisan location from Redis: {e}")
            return False
    
    async def find_nearby_artisans(
        self, 
        latitude: Decimal, 
        longitude: Decimal, 
        radius_km: float = 10.0,
        limit: int = 20
    ) -> List[Dict]:
        """Find nearby artisans using Redis geospatial queries"""
        try:
            if not cache.redis:
                return []
            
            # Convert km to meters for Redis
            radius_m = radius_km * 1000
            
            # Use GEORADIUS to find nearby artisans
            results = await cache.redis.georadius(
                self.redis_key,
                float(longitude), float(latitude),
                radius_m, unit='m',
                withdist=True, withcoord=True,
                sort='ASC', count=limit
            )
            
            nearby_artisans = []
            for result in results:
                artisan_id = int(result[0])
                distance_m = float(result[1])
                coordinates = result[2]
                
                nearby_artisans.append({
                    'artisan_id': artisan_id,
                    'distance_km': round(distance_m / 1000, 2),
                    'latitude': coordinates[1],
                    'longitude': coordinates[0]
                })
            
            return nearby_artisans
            
        except Exception as e:
            print(f"Error finding nearby artisans: {e}")
            return []
    
    async def get_artisan_location(self, artisan_id: int) -> Optional[Dict]:
        """Get artisan location from Redis"""
        try:
            if not cache.redis:
                return None
                
            # Get position from geospatial index
            positions = await cache.redis.geopos(self.redis_key, str(artisan_id))
            if positions and positions[0]:
                longitude, latitude = positions[0]
                return {
                    'latitude': latitude,
                    'longitude': longitude
                }
            return None
        except Exception as e:
            print(f"Error getting artisan location: {e}")
            return None
    
    async def calculate_distance(
        self, 
        lat1: Decimal, lon1: Decimal, 
        lat2: Decimal, lon2: Decimal
    ) -> float:
        """Calculate distance between two points using Haversine formula"""
        # Convert to radians
        lat1_rad = math.radians(float(lat1))
        lon1_rad = math.radians(float(lon1))
        lat2_rad = math.radians(float(lat2))
        lon2_rad = math.radians(float(lon2))
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = (math.sin(dlat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in kilometers
        earth_radius_km = 6371.0
        distance = earth_radius_km * c
        
        return round(distance, 2)
    
    async def get_location_stats(self) -> Dict:
        """Get statistics about artisan locations"""
        try:
            if not cache.redis:
                return {}
                
            # Get total count in geospatial index
            total_with_location = await cache.redis.zcard(self.redis_key)
            
            return {
                'artisans_with_location': total_with_location,
                'redis_key': self.redis_key
            }
        except Exception as e:
            print(f"Error getting location stats: {e}")
            return {}
    
    async def bulk_update_locations(self, artisan_locations: List[Dict]) -> int:
        """Bulk update multiple artisan locations"""
        try:
            if not cache.redis or not artisan_locations:
                return 0
                
            # Prepare data for GEOADD
            geo_data = []
            for location in artisan_locations:
                geo_data.extend([
                    float(location['longitude']),
                    float(location['latitude']),
                    str(location['artisan_id'])
                ])
            
            # Bulk add to geospatial index
            if geo_data:
                await cache.redis.geoadd(self.redis_key, *geo_data)
                return len(artisan_locations)
            
            return 0
        except Exception as e:
            print(f"Error bulk updating locations: {e}")
            return 0

# Global instance
geolocation_service = GeolocationService()