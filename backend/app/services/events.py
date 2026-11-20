# backend/app/services/events.py
"""Server-Sent Events (SSE) broadcaster for streaming pipeline progress."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """In-memory pub-sub event broadcaster for analysis jobs."""

    def __init__(self) -> None:
        self._listeners: dict[str, list[asyncio.Queue[dict[str, Any]]]] = {}
        self._last_events: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def publish(
        self,
        analysis_id: str,
        stage: str,
        percent: int,
        message: str,
        status: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Publishes an event to all subscribers of a specific analysis job."""
        event_data: dict[str, Any] = {
            "analysis_id": analysis_id,
            "stage": stage,
            "percent": percent,
            "message": message,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if extra:
            event_data.update(extra)

        self._last_events[analysis_id] = event_data

        queues = self._listeners.get(analysis_id, [])
        for q in list(queues):
            try:
                q.put_nowait(event_data)
            except Exception as e:
                logger.debug("Failed to put event into queue for %s: %s", analysis_id, e)

    def publish_sync(
        self,
        analysis_id: str,
        stage: str,
        percent: int,
        message: str,
        status: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Synchronous wrapper for thread-pool jobs."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self.publish(analysis_id, stage, percent, message, status, extra),
                    loop,
                )
                return
        except RuntimeError:
            pass

        # If no active loop in this thread, update last event directly
        event_data: dict[str, Any] = {
            "analysis_id": analysis_id,
            "stage": stage,
            "percent": percent,
            "message": message,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        if extra:
            event_data.update(extra)
        self._last_events[analysis_id] = event_data

    async def subscribe(
        self, analysis_id: str
    ) -> AsyncGenerator[str, None]:
        """Subscribes to an analysis event stream formatted for SSE."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        if analysis_id not in self._listeners:
            self._listeners[analysis_id] = []
        self._listeners[analysis_id].append(q)

        # Yield current/last state if available
        if analysis_id in self._last_events:
            last_ev = self._last_events[analysis_id]
            yield f"data: {json.dumps(last_ev)}\n\n"
            if last_ev.get("status") in {"completed", "failed"}:
                # If already finished, return immediately
                self.unsubscribe(analysis_id, q)
                return

        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("status") in {"completed", "failed"}:
                        break
                except TimeoutError:
                    # Keep-alive comment for SSE connections
                    yield ": ping\n\n"
        finally:
            self.unsubscribe(analysis_id, q)

    def unsubscribe(self, analysis_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        """Removes a listener queue."""
        if analysis_id in self._listeners:
            try:
                self._listeners[analysis_id].remove(q)
                if not self._listeners[analysis_id]:
                    del self._listeners[analysis_id]
            except ValueError:
                pass


event_broadcaster = EventBroadcaster()
