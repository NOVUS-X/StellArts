from __future__ import annotations

from collections import deque
from typing import Any


class AnalysisQueue:
    def __init__(self) -> None:
        self.queue_name = "analysis-node"
        self._jobs: deque[dict[str, Any]] = deque()

    async def enqueue(self, payload: dict[str, Any]) -> None:
        self._jobs.append(payload)

    def snapshot(self) -> list[dict[str, Any]]:
        return list(self._jobs)

    def clear(self) -> None:
        self._jobs.clear()


analysis_queue = AnalysisQueue()
