import uuid
from datetime import datetime
from decimal import Decimal

import pytest

from app.core.security import create_access_token, get_password_hash
from app.models.artisan import Artisan
from app.models.booking import Booking, BookingStatus
from app.models.client import Client
from app.models.user import User
from app.schemas.labor_pricing import UrgencyLevel
from app.services import labor_pricing_engine
from app.tests.test_crud_endpoints import get_auth_headers


@pytest.fixture(autouse=True)
def _reset_labor_hydration():
    labor_pricing_engine.clear_hydration()
    yield
    labor_pricing_engine.clear_hydration()


def _add_completed_booking(
    db,
    *,
    service: str,
    labor: float,
    zip_code: str,
) -> None:
    u_art = User(
        email=f"a{uuid.uuid4().hex[:6]}@t.com",
        hashed_password=get_password_hash("p"),
        role="artisan",
        is_active=True,
        is_verified=True,
    )
    u_cli = User(
        email=f"c{uuid.uuid4().hex[:6]}@t.com",
        hashed_password=get_password_hash("p"),
        role="client",
        is_active=True,
        is_verified=True,
    )
    db.add_all([u_art, u_cli])
    db.flush()
    art = Artisan(user_id=u_art.id, business_name="Biz")
    cli = Client(user_id=u_cli.id)
    db.add_all([art, cli])
    db.flush()
    db.add(
        Booking(
            id=uuid.uuid4(),
            client_id=cli.id,
            artisan_id=art.id,
            service=service,
            estimated_cost=Decimal(str(labor)),
            labor_cost=Decimal(str(labor)),
            status=BookingStatus.COMPLETED,
            location=f"123 Main St, Austin TX {zip_code}",
            date=datetime.utcnow(),
        )
    )
    db.commit()


def test_build_anonymized_rows_filters_non_completed(db_session):
    _add_completed_booking(
        db_session,
        service="Plumbing repair under kitchen sink",
        labor=150.0,
        zip_code="78701",
    )
    rows = labor_pricing_engine.build_anonymized_job_rows(db_session)
    assert len(rows) == 1
    assert rows[0]["zip"] == "78701"
    assert rows[0]["labor"] == 150.0


def test_suggest_local_pool_and_urgency_modifier(db_session):
    _add_completed_booking(
        db_session,
        service="Kitchen sink drain pipe replacement and seal",
        labor=200.0,
        zip_code="78701",
    )
    _add_completed_booking(
        db_session,
        service="Kitchen faucet install and supply lines",
        labor=300.0,
        zip_code="78701",
    )
    _add_completed_booking(
        db_session,
        service="Electrical outlet installation only",
        labor=500.0,
        zip_code="78701",
    )
    out = labor_pricing_engine.suggest_labor_price(
        db_session,
        sow_text="Kitchen sink drain repair and pipe replacement work",
        zip_code="78701",
        urgency=UrgencyLevel.high,
        artisan_average_rating=None,
        top_k=2,
    )
    assert out.region_scope == "local"
    assert out.matches_used == 2
    assert out.baseline_average_labor is not None
    assert out.urgency_multiplier == 1.12
    assert out.suggested_labor_price == round(out.baseline_average_labor * 1.12, 2)


def test_suggest_expanded_when_no_local_zip(db_session):
    _add_completed_booking(
        db_session,
        service="Drywall patch and paint touch up small room",
        labor=120.0,
        zip_code="10001",
    )
    out = labor_pricing_engine.suggest_labor_price(
        db_session,
        sow_text="Drywall patching and interior paint touch up",
        zip_code="78701",
        urgency=UrgencyLevel.normal,
        artisan_average_rating=None,
    )
    assert out.region_scope == "expanded"
    assert out.matches_used >= 1


def test_suggest_endpoint_requires_auth(client):
    r = client.post(
        "api/v1/pricing/labor/suggest",
        json={
            "sow_text": "Replace bathroom vanity and faucet",
            "zip_code": "78701",
            "urgency": "normal",
        },
    )
    assert r.status_code == 403


def test_suggest_endpoint_with_data(client, db_session):
    _add_completed_booking(
        db_session,
        service="Bathroom vanity replacement and faucet hookup",
        labor=400.0,
        zip_code="78701",
    )
    headers = get_auth_headers(client, "lp_client@test.com", "Pass123!", "client")
    r = client.post(
        "api/v1/pricing/labor/suggest",
        json={
            "sow_text": "Install new bathroom vanity and connect faucet",
            "zip_code": "78701",
            "urgency": "normal",
            "artisan_average_rating": 5.0,
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["region_scope"] == "local"
    assert data["suggested_labor_price"] is not None
    assert data["rating_multiplier"] > 1.0


def test_reindex_admin_only(client, db_session):
    admin = User(
        email=f"lp_admin_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("Pass123!"),
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    token = create_access_token(subject=admin.id)
    r = client.post(
        "api/v1/pricing/labor/reindex",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    assert "indexed_jobs" in r.json()
