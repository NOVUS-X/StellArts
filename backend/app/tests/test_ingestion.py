from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image
from fastapi.testclient import TestClient

from app.services.analysis_queue import analysis_queue
from app.services.media_ingestion import media_ingestion_service


def _make_image_bytes(*, brightness: int, size: tuple[int, int], blur: bool) -> bytes:
    image = Image.new("RGB", size, color=(brightness, brightness, brightness))

    if not blur:
        for x in range(0, size[0], 40):
            for y in range(0, size[1], 40):
                color = (255, 255, 255) if (x // 40 + y // 40) % 2 == 0 else (0, 0, 0)
                for dx in range(min(20, size[0] - x)):
                    for dy in range(min(20, size[1] - y)):
                        image.putpixel((x + dx, y + dy), color)

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_ingestion_accepts_and_queues_multimodal_payload(client: TestClient):
    analysis_queue.clear()

    photo = _make_image_bytes(brightness=170, size=(1600, 1200), blur=False)
    audio = b"voice-note" * 2000
    video = b"\x00\x00\x00\x20ftypisom" + (b"video-frame" * 60000)

    with client.websocket_connect("/api/v1/ingestion/ws/session-123") as websocket:
        response = client.post(
            "/api/v1/ingestion/vision-to-scope",
            data={"session_id": "session-123", "client_reference": "ISSUE-152"},
            files=[
                ("photos", ("beam.png", photo, "image/png")),
                ("voice_notes", ("walkthrough.m4a", audio, "audio/mp4")),
                ("videos", ("site.mp4", video, "video/mp4")),
            ],
        )
        websocket_message = websocket.receive_json()

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["forwarded_to_queue"] is True
    assert payload["feedback"] == []
    assert len(payload["stored_media"]) == 3

    queued_jobs = analysis_queue.snapshot()
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["job_id"] == payload["job_id"]
    assert queued_jobs[0]["client_reference"] == "ISSUE-152"
    assert websocket_message["payload"]["status"] == "accepted"

    for media in payload["stored_media"]:
        assert Path(media["storage_path"]).exists()

    analysis_queue.clear()
    media_ingestion_service._cleanup(payload["job_id"])


def test_ingestion_rejects_dark_or_low_quality_media(client: TestClient):
    analysis_queue.clear()

    dark_photo = _make_image_bytes(brightness=12, size=(1600, 1200), blur=False)

    response = client.post(
        "/api/v1/ingestion/vision-to-scope",
        data={"session_id": "session-456"},
        files=[("photos", ("beam-dark.png", dark_photo, "image/png"))],
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "rejected"
    assert payload["forwarded_to_queue"] is False
    assert payload["stored_media"] == []
    assert any(item["code"] == "photo_too_dark" for item in payload["feedback"])
    assert analysis_queue.snapshot() == []
