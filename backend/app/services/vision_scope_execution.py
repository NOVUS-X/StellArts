from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.core.config import settings
from app.schemas.project_state import ProjectState, VisionAnalysisJob, VisionExecutionMetadata


class StructuredVisionClient(Protocol):
    async def generate_project_state(
        self,
        *,
        prompt: str,
        media_parts: list[dict[str, Any]],
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        ...


class GeminiVisionClient:
    def __init__(
        self,
        *,
        api_key: str,
        model_name: str,
        api_base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def generate_project_state(
        self,
        *,
        prompt: str,
        media_parts: list[dict[str, Any]],
        response_schema: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}, *media_parts],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": response_schema,
                "temperature": 0,
            },
        }

        url = (
            f"{self.api_base_url}/models/{self.model_name}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        response_payload = response.json()
        candidates = response_payload.get("candidates") or []
        if not candidates:
            raise ValueError("Gemini returned no candidates for vision scope analysis.")

        parts = candidates[0].get("content", {}).get("parts", [])
        text_segments = [part.get("text", "") for part in parts if part.get("text")]
        if not text_segments:
            raise ValueError("Gemini returned no JSON text for vision scope analysis.")

        return json.loads("".join(text_segments))


class VisionScopeExecutionNode:
    def __init__(
        self,
        client: StructuredVisionClient | None = None,
    ) -> None:
        self.client = client or self._build_default_client()

    async def execute(self, payload: dict[str, Any] | VisionAnalysisJob) -> ProjectState:
        job = payload if isinstance(payload, VisionAnalysisJob) else VisionAnalysisJob.model_validate(payload)
        prompt = self._build_prompt(job)
        media_parts = self._build_media_parts(job)
        result = await self.client.generate_project_state(
            prompt=prompt,
            media_parts=media_parts,
            response_schema=_gemini_json_schema(ProjectState.model_json_schema()),
        )

        enriched_result = {
            **result,
            "job_id": job.job_id,
            "session_id": job.session_id,
            "client_reference": job.client_reference,
            "status": "scoped",
            "source_media": [media.model_dump() for media in job.media],
            "model_name": result.get("model_name") or settings.VISION_SCOPE_MODEL,
        }
        return ProjectState.model_validate(enriched_result)

    async def execute_with_metadata(
        self, payload: dict[str, Any] | VisionAnalysisJob
    ) -> tuple[ProjectState, VisionExecutionMetadata]:
        job = payload if isinstance(payload, VisionAnalysisJob) else VisionAnalysisJob.model_validate(payload)
        prompt = self._build_prompt(job)
        media_parts = self._build_media_parts(job)
        raw_response = await self.client.generate_project_state(
            prompt=prompt,
            media_parts=media_parts,
            response_schema=_gemini_json_schema(ProjectState.model_json_schema()),
        )
        state = ProjectState.model_validate(
            {
                **raw_response,
                "job_id": job.job_id,
                "session_id": job.session_id,
                "client_reference": job.client_reference,
                "status": "scoped",
                "source_media": [media.model_dump() for media in job.media],
                "model_name": raw_response.get("model_name") or settings.VISION_SCOPE_MODEL,
            }
        )
        metadata = VisionExecutionMetadata(
            model_name=state.model_name,
            media_parts_sent=len(media_parts),
            prompt_preview=prompt[:500],
            raw_response=raw_response,
        )
        return state, metadata

    def _build_default_client(self) -> StructuredVisionClient:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is required to execute the vision-to-scope node."
            )

        return GeminiVisionClient(
            api_key=settings.GEMINI_API_KEY,
            model_name=settings.VISION_SCOPE_MODEL,
            api_base_url=settings.GEMINI_API_BASE_URL,
            timeout_seconds=settings.VISION_SCOPE_TIMEOUT_SECONDS,
        )

    def _build_prompt(self, job: VisionAnalysisJob) -> str:
        media_summary = "\n".join(
            [
                (
                    f"- {media.media_type}: {media.filename} "
                    f"(content_type={media.content_type}, size_bytes={media.size_bytes}, "
                    f"metadata={json.dumps(media.metadata, sort_keys=True)})"
                )
                for media in job.media
            ]
        )

        transcript_block = job.transcript or "No transcript supplied."
        site_notes_block = job.site_notes or "No site notes supplied."

        return (
            "You are the Vision-to-Scope execution node for StellArts.\n"
            "Analyze the validated multimodal payload and extract only what is visually or contextually supported.\n"
            "Return JSON that matches the provided schema exactly.\n"
            "Focus on three things: required materials, structural damage, and scope constraints.\n"
            "If square footage or dimensions are approximate, preserve that uncertainty in notes or dimensions while "
            "still providing a best-effort numeric area_sq_ft when evidence supports it.\n"
            "Do not invent materials or damages that are not supported by the evidence.\n\n"
            f"Job ID: {job.job_id}\n"
            f"Session ID: {job.session_id or 'n/a'}\n"
            f"Client Reference: {job.client_reference or 'n/a'}\n"
            f"Job Status: {job.status}\n"
            "Validated Media:\n"
            f"{media_summary or '- none'}\n\n"
            "Transcript:\n"
            f"{transcript_block}\n\n"
            "Site Notes:\n"
            f"{site_notes_block}\n"
        )

    def _build_media_parts(self, job: VisionAnalysisJob) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []

        for media in job.media:
            path = Path(media.storage_path)
            if not path.exists():
                continue

            if media.media_type != "photo":
                continue

            encoded_bytes = base64.b64encode(path.read_bytes()).decode("utf-8")
            parts.append(
                {
                    "inlineData": {
                        "mimeType": media.content_type,
                        "data": encoded_bytes,
                    }
                }
            )

        return parts


vision_scope_execution_node = VisionScopeExecutionNode


def _gemini_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {
        "$id",
        "$defs",
        "$ref",
        "$anchor",
        "type",
        "format",
        "title",
        "description",
        "enum",
        "items",
        "prefixItems",
        "minItems",
        "maxItems",
        "minimum",
        "maximum",
        "anyOf",
        "oneOf",
        "properties",
        "additionalProperties",
        "required",
    }

    if isinstance(schema, dict):
        if "properties" in schema:
            sanitized = {
                key: _gemini_json_schema(value)
                for key, value in schema.items()
                if key in allowed_keys and key != "properties"
            }
            sanitized["properties"] = {
                property_name: _gemini_json_schema(property_schema)
                for property_name, property_schema in schema["properties"].items()
            }
            return sanitized

        if "$defs" in schema:
            sanitized = {
                key: _gemini_json_schema(value)
                for key, value in schema.items()
                if key in allowed_keys and key != "$defs"
            }
            sanitized["$defs"] = {
                definition_name: _gemini_json_schema(definition_schema)
                for definition_name, definition_schema in schema["$defs"].items()
            }
            return sanitized

        sanitized: dict[str, Any] = {}
        for key, value in schema.items():
            if key not in allowed_keys:
                continue
            sanitized[key] = _gemini_json_schema(value)
        return sanitized

    if isinstance(schema, list):
        return [_gemini_json_schema(item) for item in schema]

    return schema
