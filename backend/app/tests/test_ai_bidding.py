import pytest
from decimal import Decimal
from app.services.ai_service import ai_service
from app.schemas.booking import BidCreate

def test_calculate_bid_range_plumbing():
    service_desc = "Fixing a leaky plumbing pipe"
    hourly_rate = Decimal("50.00")
    estimated_hours = 2.0
    
    result = ai_service.calculate_bid_range(service_desc, hourly_rate, estimated_hours)
    
    # Plumbing cost = 80.00, Labor = 50 * 2 = 100.00, Total = 180.00
    assert result["material_cost"] == Decimal("80.00")
    assert result["labor_cost"] == Decimal("100.00")
    assert result["total_estimated"] == Decimal("180.00")
    assert result["range_min"] == Decimal("180.00") * Decimal("0.9")
    assert result["range_max"] == Decimal("180.00") * Decimal("1.1")

def test_calculate_bid_range_default():
    service_desc = "General consultation"
    hourly_rate = Decimal("40.00")
    estimated_hours = 1.0
    
    result = ai_service.calculate_bid_range(service_desc, hourly_rate, estimated_hours)
    
    # Default material cost = 30.00, Labor = 40 * 1 = 40.00, Total = 70.00
    assert result["material_cost"] == Decimal("30.00")
    assert result["labor_cost"] == Decimal("40.00")
    assert result["total_estimated"] == Decimal("70.00")

def test_generate_smart_pitch():
    service_desc = "Electrical work"
    material_cost = Decimal("60.00")
    labor_cost = Decimal("150.00")
    total_cost = Decimal("210.00")
    estimated_hours = 3.0
    
    pitch = ai_service.generate_smart_pitch(service_desc, material_cost, labor_cost, total_cost, estimated_hours)
    
    assert "I estimate materials at $60.00" in pitch
    assert "Claim this 3.0hr job for $210.00?" in pitch

def test_guardrail_check_pass():
    # Range max = 200, Bid = 500 (250%) -> Pass
    range_max = Decimal("200.00")
    bid = Decimal("500.00")
    is_outlier = ai_service.check_guardrail(bid, range_max)
    assert is_outlier is False

def test_guardrail_check_fail():
    # Range max = 200, Bid = 700 (350%) -> Fail
    range_max = Decimal("200.00")
    bid = Decimal("700.00")
    is_outlier = ai_service.check_guardrail(bid, range_max)
    assert is_outlier is True

def test_bid_create_schema():
    bid = BidCreate(bid_amount=150.0)
    assert bid.bid_amount == 150.0
    assert bid.justification is None
    
    bid_with_just = BidCreate(bid_amount=700.0, justification="High quality parts")
    assert bid_with_just.justification == "High quality parts"
