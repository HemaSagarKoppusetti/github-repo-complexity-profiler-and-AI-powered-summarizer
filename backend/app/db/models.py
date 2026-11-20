# backend/app/db/models.py
"""SQLAlchemy database models."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    github_url: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="queued", index=True
    )  # queued, running, completed, failed
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    percent: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending, completed, failed, skipped

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("idx_analyses_url_created", "github_url", "created_at"),
    )

    def get_result(self) -> dict[str, Any] | None:
        if not self.result_json:
            return None
        try:
            return json.loads(self.result_json)
        except Exception:
            return None

    def set_result(self, data: dict[str, Any]) -> None:
        self.result_json = json.dumps(data)
