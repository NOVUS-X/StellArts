from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pydantic import ValidationError

from app.schemas.ingestion import StoredMedia
from app.services.vision_scope_execution import VisionScopeExecutionNode


class FakeVisionClient:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[dict] = []

    async def generate_project_state(self, *, prompt, media_parts, response_schema):
        self.calls.append(
            {
                "prompt": prompt,
                "media_parts": media_parts,
                "response_schema": response_schema,
            }
        )
        return self.response


def _make_scope_image(path: Path) -> None:
    image = Image.new("RGB", (1600, 1200), color=(188, 168, 120))
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 160, 1460, 1020), outline=(82, 49, 24), width=12)
    draw.rectangle((280, 400, 880, 900), fill=(70, 40, 22))
    draw.line((900, 460, 1360, 920), fill=(20, 20, 20), width=18)
    draw.text((250, 280), "Deck repair approx 15 sq ft", fill=(0, 0, 0))
    image.save(path, format="PNG")


def _build_payload(image_path: Path) -> dict:
    return {
        "job_id": "job-vision-153",
        "session_id": "session-vision-153",
        "client_reference": "ISSUE-153",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "queued_for_analysis",
        "transcript": (
            "Replace the rotting joists and use pressure-treated pine. "
            "The damaged section is about 15 square feet near the back-left corner."
        ),
        "site_notes": "Visible deck framing damage around the left rear perimeter.",
        "media": [
            StoredMedia(
                media_type="photo",
                filename="deck-damage.png",
                content_type="image/png",
                size_bytes=image_path.stat().st_size,
                storage_path=str(image_path),
                metadata={"width": 1600, "height": 1200, "brightness": 138.4},
            ).model_dump()
        ],
    }


def test_vision_scope_execution_extracts_materials_damage_and_scope(tmp_path: Path):
    image_path = tmp_path / "deck-damage.png"
    _make_scope_image(image_path)

    fake_client = FakeVisionClient(
        {
            "summary": "Replace damaged deck framing in an approximately 15 sq ft area.",
            "required_materials": [
                {
                    "name": "Pressure-treated pine",
                    "quantity": "Enough to replace joists in the damaged section",
                    "notes": "Match existing outdoor framing dimensions.",
                    "confidence": 0.97,
                }
            ],
            "structural_damage": [
                {
                    "type": "Rotting joists",
                    "location": "Back-left corner of the deck framing",
                    "severity": "high",
                    "notes": "Darkened and deteriorated framing members are visible.",
                    "confidence": 0.95,
                }
            ],
            "scope_constraints": {
                "area_sq_ft": 15,
                "dimensions": "~15 sq ft",
                "access_constraints": [],
                "safety_constraints": ["Repair structural members before surface restoration."],
                "additional_notes": ["Approximation based on visible damage and transcript."],
            },
            "model_name": "fake-gemini-2.5-pro",
        }
    )
    node = VisionScopeExecutionNode(client=fake_client)

    state = asyncio.run(node.execute(_build_payload(image_path)))

    assert state.status == "scoped"
    assert state.required_materials[0].name == "Pressure-treated pine"
    assert state.structural_damage[0].type == "Rotting joists"
    assert state.scope_constraints.area_sq_ft == 15
    assert state.scope_constraints.dimensions == "~15 sq ft"
    assert state.source_media[0].filename == "deck-damage.png"

    assert len(fake_client.calls) == 1
    assert "pressure-treated pine" in fake_client.calls[0]["prompt"].lower()
    assert "15 square feet" in fake_client.calls[0]["prompt"]
    assert len(fake_client.calls[0]["media_parts"]) == 1
    assert fake_client.calls[0]["media_parts"][0]["inlineData"]["mimeType"] == "image/png"

    schema = fake_client.calls[0]["response_schema"]
    assert schema["type"] == "object"
    assert "required_materials" in schema["properties"]
    assert schema["additionalProperties"] is False


def test_vision_scope_execution_rejects_nonconforming_llm_output(tmp_path: Path):
    image_path = tmp_path / "deck-damage.png"
    _make_scope_image(image_path)

    fake_client = FakeVisionClient(
        {
            "summary": "Missing required nested fields should fail validation.",
            "required_materials": [
                {
                    "name": "Pressure-treated pine",
                    "confidence": 1.2,
                    "unexpected": "not allowed",
                }
            ],
            "structural_damage": [
                {
                    "type": "Rotting joists",
                    "confidence": 0.9,
                }
            ],
            "scope_constraints": {"dimensions": "~15 sq ft"},
            "model_name": "fake-gemini-2.5-pro",
        }
    )
    node = VisionScopeExecutionNode(client=fake_client)

    with pytest.raises(ValidationError):
        asyncio.run(node.execute(_build_payload(image_path)))


def test_project_state_endpoint_executes_with_injected_fake_client(client, monkeypatch, tmp_path: Path):
    image_path = tmp_path / "deck-damage.png"
    _make_scope_image(image_path)

    fake_client = FakeVisionClient(
        {
            "summary": "Replace damaged deck framing in an approximately 15 sq ft area.",
            "required_materials": [
                {
                    "name": "Pressure-treated pine",
                    "quantity": "Replacement joists",
                    "notes": None,
                    "confidence": 0.94,
                }
            ],
            "structural_damage": [
                {
                    "type": "Rotting joists",
                    "location": "Back-left corner",
                    "severity": "high",
                    "notes": None,
                    "confidence": 0.93,
                }
            ],
            "scope_constraints": {
                "area_sq_ft": 15,
                "dimensions": "~15 sq ft",
                "access_constraints": [],
                "safety_constraints": [],
                "additional_notes": [],
            },
            "model_name": "fake-gemini-2.5-pro",
        }
    )

    from app.api.v1.endpoints import ingestion as ingestion_endpoint

    async def _fake_execute(payload):
        node = VisionScopeExecutionNode(client=fake_client)
        return await node.execute(payload)

    class StubNode:
        async def execute(self, payload):
            return await _fake_execute(payload)

    monkeypatch.setattr(ingestion_endpoint, "VisionScopeExecutionNode", lambda: StubNode())

    response = client.post(
        "/api/v1/ingestion/vision-to-scope/execute",
        json={"payload": _build_payload(image_path)},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "scoped"
    assert data["required_materials"][0]["name"] == "Pressure-treated pine"
    assert data["structural_damage"][0]["type"] == "Rotting joists"
    assert data["scope_constraints"]["area_sq_ft"] == 15
