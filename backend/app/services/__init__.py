from sqlalchemy.orm import Session
from app.models.artisan import Artisan
from app.models.booking import Booking
from app.models.user import User
from typing import List, Optional, Dict, Any
from datetime import datetime


class NotificationService:
    """
    Service for handling notifications to artisans about new bookings.
    """

    @staticmethod
    def dispatch_smart_pitch(artisan: Artisan, booking: Booking, pitch_message: str) -> dict:
        """
        Send a smart pitch message to an artisan for a new booking.
        """
        # In a real implementation, this would send SMS, push notification, or email
        # For now, we'll just log the dispatch
        
        dispatch_record = {
            "artisan_id": artisan.id,
            "booking_id": booking.id,
            "message": pitch_message,
            "dispatched_at": datetime.utcnow().isoformat(),
            "status": "dispatched",
            "contact_method": "sms"  # Could be email, push, etc.
        }
        
        print(f"📱 Dispatching to artisan {artisan.id}: {pitch_message}")
        
        return dispatch_record

    @staticmethod
    async def find_top_matched_artisans(
        db: Session, booking: Booking, limit: int = 5
    ) -> List[Artisan]:
        """
        Find the top matched artisans for a booking based on location and service.
        """
        # For now, simple service matching
        # In a real implementation, this would use more sophisticated matching
        
        artisans = (
            db.query(Artisan)
            .filter(
                Artisan.is_verified == True,
                Artisan.is_available == True
            )
            .limit(limit)
            .all()
        )
        
        return artisans

    @staticmethod
    async def dispatch_to_matched_artisans(
        db: Session, 
        booking: Booking, 
        limit: int = 5
    ) -> List[dict]:
        """
        Dispatch booking to matched artisans.
        """
        matched_artisans = await NotificationService.find_top_matched_artisans(
            db, booking, limit
        )
        
        dispatch_results = []
        for artisan in matched_artisans:
            result = NotificationService.dispatch_smart_pitch(
                artisan, booking, booking.artisan_pitch
            )
            dispatch_results.append(result)
        
        return dispatch_results


notification_service = NotificationService()


class GeoFenceService:
    """
    Service for handling GPS location updates and geo-fence verification.
    """

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.
        Returns distance in meters.
        """
        import math
        
        # Earth radius in meters
        R = 6371000
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        # Haversine formula
        a = (
            math.sin(delta_lat / 2) ** 2 +
            math.cos(lat1_rad) * math.cos(lat2_rad) *
            math.sin(delta_lon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    @staticmethod
    def is_within_geofence(
        artisan_lat: float,
        artisan_lon: float,
        job_lat: float,
        job_lon: float,
        radius_meters: float = 100.0
    ) -> bool:
        """
        Check if artisan is within specified radius of job location.
        Default radius is 100 meters.
        """
        distance = GeoFenceService.calculate_distance(
            artisan_lat, artisan_lon, job_lat, job_lon
        )
        return distance <= radius_meters

    @staticmethod
    def verify_arrival(
        booking: Booking, 
        artisan_location: Dict[str, Any], 
        radius_meters: float = 100.0
    ) -> Dict[str, Any]:
        """
        Verify if artisan has arrived at job location.
        """
        if not booking.location:
            return {
                "verified": False,
                "reason": "Job location not specified",
                "distance": None
            }
        
        if not artisan_location.get("latitude") or not artisan_location.get("longitude"):
            return {
                "verified": False,
                "reason": "Artisan location not provided",
                "distance": None
            }
        
        # Parse job location (could be coordinates or address)
        try:
            if "," in booking.location:
                # Coordinates format: "lat,lon"
                job_lat, job_lon = map(float, booking.location.split(","))
            else:
                # Address - for demo, use default NYC coordinates
                job_lat, job_lon = 40.7128, -74.0060
        except:
            job_lat, job_lon = 40.7128, -74.0060
        
        artisan_lat = artisan_location["latitude"]
        artisan_lon = artisan_location["longitude"]
        
        distance = GeoFenceService.calculate_distance(
            artisan_lat, artisan_lon, job_lat, job_lon
        )
        
        within_radius = distance <= radius_meters
        
        return {
            "verified": within_radius,
            "within_radius": within_radius,
            "distance": distance,
            "job_coordinates": {"latitude": job_lat, "longitude": job_lon},
            "artisan_coordinates": {
                "latitude": artisan_lat, 
                "longitude": artisan_lon
            },
            "radius_meters": radius_meters,
            "reason": None if within_radius else f"Artisan is {distance - radius_meters:.1f}m outside geo-fence"
        }


class OracleService:
    """
    Oracle service for interacting with Soroban smart contracts.
    Handles GPS-verified state transitions.
    """

    def __init__(self):
        self.oracle_secret_key = None
        self.oracle_public_key = None
        self.contract_address = None
        self.network_passphrase = "Test SDF Network ; September 2015"

    def initialize(self, oracle_secret_key: str, contract_address: str):
        """
        Initialize the Oracle with credentials and contract address.
        """
        from stellar_sdk import Keypair

        self.oracle_keypair = Keypair.from_secret(oracle_secret_key)
        self.oracle_secret_key = oracle_secret_key
        self.oracle_public_key = self.oracle_keypair.public_key
        self.contract_address = contract_address

    async def mark_arrival_on_chain(self, engagement_id: int) -> dict:
        """
        Mark artisan arrival on the blockchain after GPS verification.
        Transitions escrow from Funded to InProgress state.
        """
        try:
            from stellar_sdk import TransactionBuilder, Network
            from stellar_sdk.soroban import SorobanServer
            from stellar_sdk.soroban.types import Address

            server = SorobanServer("https://soroban-testnet.stellar.org")

            # Get account info
            oracle_account = server.load_account(self.oracle_public_key)

            # Build transaction to call mark_arrived
            transaction = (
                TransactionBuilder(
                    source_account=oracle_account,
                    network_passphrase=self.network_passphrase,
                    base_fee=100,
                )
                .add_contract_call(
                    contract_id=self.contract_address,
                    function_name="mark_arrived",
                    args=[
                        engagement_id,
                        Address(self.oracle_public_key),
                    ],
                )
                .set_timeout(300)
                .build()
            )

            # Simulate transaction
            simulate_result = server.simulate_transaction(transaction)

            if simulate_result.error:
                return {
                    "success": False,
                    "error": simulate_result.error,
                    "engagement_id": engagement_id
                }

            # Set simulation data and sign
            transaction.set_simulation_results(simulate_result)
            transaction.sign(self.oracle_keypair)

            # Submit transaction
            send_result = server.send_transaction(transaction)

            if send_result.status != "PENDING":
                return {
                    "success": False,
                    "error": f"Transaction failed: {send_result.status}",
                    "engagement_id": engagement_id
                }

            # Wait for confirmation
            import time
            time.sleep(3)

            get_result = server.get_transaction(send_result.hash)

            if get_result.status == "SUCCESS":
                return {
                    "success": True,
                    "transaction_hash": send_result.hash.hex(),
                    "engagement_id": engagement_id,
                    "status": "InProgress"
                }
            else:
                return {
                    "success": False,
                    "error": f"Transaction failed: {get_result.result_xdr}",
                    "engagement_id": engagement_id
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "engagement_id": engagement_id
            }

    def get_contract_status(self, engagement_id: int) -> dict:
        """
        Get the current status of an escrow contract.
        """
        try:
            from stellar_sdk.soroban import SorobanServer

            server = SorobanServer("https://soroban-testnet.stellar.org")

            # Query contract for escrow status
            result = server.get_contract_data(
                contract_id=self.contract_address,
                key=f"Escrow({engagement_id})"
            )

            if result.val:
                return {
                    "success": True,
                    "engagement_id": engagement_id,
                    "status": result.val.status,
                    "found": True
                }
            else:
                return {
                    "success": False,
                    "error": "Escrow not found",
                    "engagement_id": engagement_id,
                    "found": False
                }

        except Exception as e:
            return {"success": False, "error": str(e), "engagement_id": engagement_id}


geo_fence_service = GeoFenceService()
oracle_service = OracleService()
