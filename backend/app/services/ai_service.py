from decimal import Decimal


class AIService:
    """
    AI Service for generating smart bids, drafting pitches, and enforcing guardrails.
    """

    @staticmethod
    def calculate_bid_range(
        service_description: str, hourly_rate: Decimal, estimated_hours: float
    ) -> dict:
        """
        Merge labor and materials into an optimal Bid Range.
        Heuristic: Basic material estimation based on service keywords.
        """
        # Default material costs based on common services
        material_estimates = {
            "plumbing": Decimal("80.00"),
            "electrical": Decimal("60.00"),
            "painting": Decimal("100.00"),
            "carpentry": Decimal("120.00"),
            "cleaning": Decimal("20.00"),
        }

        # Determine material cost based on keywords
        material_cost = Decimal("30.00")  # Default
        desc_lower = service_description.lower()
        for keyword, cost in material_estimates.items():
            if keyword in desc_lower:
                material_cost = cost
                break

        labor_cost = Decimal(str(estimated_hours)) * hourly_rate
        total_estimated = labor_cost + material_cost

        # Optimal Range: +/- 10%
        range_min = total_estimated * Decimal("0.9")
        range_max = total_estimated * Decimal("1.1")

        return {
            "labor_cost": labor_cost,
            "material_cost": material_cost,
            "range_min": range_min,
            "range_max": range_max,
            "total_estimated": total_estimated,
        }

    @staticmethod
    def generate_smart_pitch(
        service_description: str,
        material_cost: Decimal,
        labor_cost: Decimal,
        total_cost: Decimal,
        estimated_hours: float,
    ) -> str:
        """
        Draft custom push notifications/pitches.
        Example: "I estimate materials at $120. Claim this 4hr job for $600?"
        """
        return f"I estimate materials at ${material_cost:.2f}. Claim this {estimated_hours}hr job for ${total_cost:.2f}?"

    @staticmethod
    def check_guardrail(counter_offer: Decimal, range_max: Decimal) -> bool:
        """
        Enforce market guardrails.
        Returns True if the counter-offer is > 300% of the calculated max range.
        """
        return counter_offer > (range_max * Decimal("3.0"))


ai_service = AIService()
