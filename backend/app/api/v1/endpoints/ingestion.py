from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, File, Form, UploadFile, WebSocket, WebSocketDisconnect, status

from app.schemas.ingestion import VisionToScopeResponse
from app.schemas.project_state import ProjectState, VisionExecutionRequest
from app.services.analysis_queue import analysis_queue
from app.services.ingestion_realtime import ingestion_connection_manager
from app.services.media_ingestion import build_job_payload, media_ingestion_service
from app.services.vision_scope_execution import VisionScopeExecutionNode

router = APIRouter(prefix="/ingestion")


@router.post(
    "/vision-to-scope",
    response_model=VisionToScopeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_vision_to_scope(
    session_id: str | None = Form(default=None),
    client_reference: str | None = Form(default=None),
    photos: list[UploadFile] = File(default=[]),
    videos: list[UploadFile] = File(default=[]),
    voice_notes: list[UploadFile] = File(default=[]),
):
    job_id = str(uuid4())
    result = await media_ingestion_service.process(
        job_id=job_id,
        photos=photos,
        videos=videos,
        voice_notes=voice_notes,
    )

    if result.accepted:
        payload = build_job_payload(
            job_id=job_id,
            session_id=session_id,
            client_reference=client_reference,
            stored_media=result.stored_media,
        )
        await analysis_queue.enqueue(payload)

        response = VisionToScopeResponse(
            job_id=job_id,
            session_id=session_id,
            status="accepted",
            forwarded_to_queue=True,
            queue_name=analysis_queue.queue_name,
            feedback=[],
            stored_media=result.stored_media,
            created_at=datetime.now(UTC),
        )
    else:
        response = VisionToScopeResponse(
            job_id=job_id,
            session_id=session_id,
            status="rejected",
            forwarded_to_queue=False,
            queue_name=analysis_queue.queue_name,
            feedback=result.feedback,
            stored_media=[],
            created_at=datetime.now(UTC),
        )

    await ingestion_connection_manager.publish(
        session_id,
        {
            "event": "vision_to_scope.validation",
            "payload": response.model_dump(mode="json"),
        },
    )

    return response


@router.post(
    "/vision-to-scope/execute",
    response_model=ProjectState,
    status_code=status.HTTP_200_OK,
)
async def execute_vision_to_scope(request: VisionExecutionRequest):
    node = VisionScopeExecutionNode()
    project_state = await node.execute(request.payload)

    await ingestion_connection_manager.publish(
        request.payload.session_id,
        {
            "event": "vision_to_scope.executed",
            "payload": project_state.model_dump(mode="json"),
        },
    )

    return project_state


@router.websocket("/ws/{session_id}")
async def ingestion_updates(session_id: str, websocket: WebSocket):
    await ingestion_connection_manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ingestion_connection_manager.disconnect(session_id, websocket)
