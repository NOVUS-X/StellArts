from __future__ import annotations

import json
import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIService:
    """Analyze job requests with an OpenAI/Gemini-compatible API and safe fallbacks."""

    SPECIALTIES = (
        "Plumbing",
        "Water Heater",
        "Electrical",
        "Painting",
        "Carpentry",
        "Cleaning",
        "HVAC",
        "Appliance Repair",
        "Roofing",
        "Landscaping",
        "Locksmith",
        "General Handyman",
    )

    @staticmethod
    def _fallback(
        description: str, location: str | None = None, hours: float | None = None
    ) -> dict[str, Any]:
        text = description.lower()
        keyword_tags = {
            "plumb": ["Plumbing"],
            "sink": ["Plumbing"],
            "faucet": ["Plumbing"],
            "pipe": ["Plumbing"],
            "water heater": ["Plumbing", "Water Heater"],
            "boiler": ["Water Heater"],
            "electri": ["Electrical"],
            "paint": ["Painting"],
            "carpent": ["Carpentry"],
            "clean": ["Cleaning"],
            "air condition": ["HVAC"],
            " hvac": ["HVAC"],
            "appliance": ["Appliance Repair"],
            "roof": ["Roofing"],
            "garden": ["Landscaping"],
            "lock": ["Locksmith"],
        }
        tags: list[str] = []
        for keyword, values in keyword_tags.items():
            if keyword in text:
                for value in values:
                    if value not in tags:
                        tags.append(value)
        if not tags:
            tags = ["General Handyman"]

        base_costs = {
            "Plumbing": Decimal("120"),
            "Water Heater": Decimal("250"),
            "Electrical": Decimal("140"),
            "Painting": Decimal("180"),
            "Carpentry": Decimal("200"),
            "Cleaning": Decimal("90"),
            "HVAC": Decimal("220"),
            "Appliance Repair": Decimal("160"),
            "Roofing": Decimal("300"),
            "Landscaping": Decimal("120"),
            "Locksmith": Decimal("110"),
            "General Handyman": Decimal("100"),
        }
        hours_value = Decimal(str(hours or 2))
        total = max(base_costs[tags[0]], Decimal("50")) + (hours_value * Decimal("50"))
        minimum = (total * Decimal("0.8")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        maximum = (total * Decimal("1.25")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return {
            "specialties": tags,
            "estimated_hours": float(hours_value),
            "range_min": float(minimum),
            "range_max": float(maximum),
            "estimated_cost": float(
                ((minimum + maximum) / 2).quantize(Decimal("0.01"))
            ),
            "confidence": 0.35,
        }

    async def analyze_job(
        self,
        description: str,
        location: str | None = None,
        estimated_hours: float | None = None,
    ) -> dict[str, Any]:
        fallback = self._fallback(description, location, estimated_hours)
        if not settings.AI_API_URL or not settings.AI_API_KEY:
            return fallback

        schema = {
            "type": "object",
            "properties": {
                "specialties": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(self.SPECIALTIES)},
                    "minItems": 1,
                    "maxItems": 4,
                },
                "estimated_hours": {"type": "number", "minimum": 0.5},
                "range_min": {"type": "number", "minimum": 1},
                "range_max": {"type": "number", "minimum": 1},
                "estimated_cost": {"type": "number", "minimum": 1},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": [
                "specialties",
                "estimated_hours",
                "range_min",
                "range_max",
                "estimated_cost",
                "confidence",
            ],
            "additionalProperties": False,
        }
        prompt = (
            "Classify this home-service job and estimate a realistic customer price range. "
            "Use the location only as a market context; do not invent an address. "
            "Return only the requested JSON.\n"
            f"Description: {description}\nLocation: {location or 'Not provided'}\n"
            f"Client supplied hours: {estimated_hours or 'Not provided'}\n"
            f"Allowed specialties: {', '.join(self.SPECIALTIES)}"
        )
        payload = {
            "model": settings.AI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise home-services triage and pricing assistant.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "job_analysis",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    settings.AI_API_URL.rstrip("/") + "/chat/completions",
                    headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                result = json.loads(content)
                tags = [tag for tag in result["specialties"] if tag in self.SPECIALTIES]
                minimum = float(result["range_min"])
                maximum = max(minimum, float(result["range_max"]))
                return {
                    **result,
                    "specialties": tags or fallback["specialties"],
                    "range_min": minimum,
                    "range_max": maximum,
                    "estimated_cost": float(result["estimated_cost"]),
                }
        except Exception as exc:
            logger.warning("Job AI analysis failed; using fallback: %s", exc)
            return fallback

    @staticmethod
    def calculate_bid_range(
        service_description: str, hourly_rate: Decimal, estimated_hours: float
    ) -> dict:
        material_estimates = {
            "plumbing": Decimal("80.00"),
            "electrical": Decimal("60.00"),
            "painting": Decimal("100.00"),
            "carpentry": Decimal("120.00"),
            "cleaning": Decimal("20.00"),
        }
        material_cost = next(
            (
                cost
                for keyword, cost in material_estimates.items()
                if keyword in service_description.lower()
            ),
            Decimal("30.00"),
        )
        labor_cost = Decimal(str(estimated_hours)) * hourly_rate
        total_estimated = labor_cost + material_cost
        return {
            "labor_cost": labor_cost,
            "material_cost": material_cost,
            "range_min": total_estimated * Decimal("0.9"),
            "range_max": total_estimated * Decimal("1.1"),
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
        return f"I estimate materials at ${material_cost:.2f}. Claim this {estimated_hours}hr job for ${total_cost:.2f}?"

    @staticmethod
    def check_guardrail(counter_offer: Decimal, range_max: Decimal) -> bool:
        return counter_offer > (range_max * Decimal("3.0"))


ai_service = AIService()


__all__ = ["AIService", "ai_service"]
