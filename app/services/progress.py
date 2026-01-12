import json
from datetime import datetime
from typing import Optional
from app.core.redis_clients import get_sync_redis
from app.schemas.rca import RCARunStatus, ProgressEvent


class ProgressService:
    """Service for publishing and tracking RCA job progress via Redis."""

    def __init__(self):
        self.redis = get_sync_redis()

    def _status_key(self, rca_run_id: str) -> str:
        return f"rca:{rca_run_id}:status"

    def _channel_name(self, rca_run_id: str) -> str:
        return f"rca:{rca_run_id}"

    def publish_progress(
        self,
        rca_run_id: str,
        status: RCARunStatus,
        step: str,
        pct: int,
        message: str,
    ) -> None:
        """Publish progress update to Redis pub/sub and update status hash."""
        event = ProgressEvent(
            status=status,
            step=step,
            pct=pct,
            message=message,
            updated_at=datetime.utcnow(),
        )

        # Update status hash
        status_data = event.model_dump()
        status_data["updated_at"] = status_data["updated_at"].isoformat()
        status_data["status"] = status_data["status"].value
        self.redis.hset(
            self._status_key(rca_run_id),
            mapping=status_data,
        )

        # Publish to channel
        self.redis.publish(
            self._channel_name(rca_run_id),
            json.dumps(status_data),
        )

    def get_latest_status(self, rca_run_id: str) -> Optional[dict]:
        """Get the latest status snapshot from Redis hash."""
        data = self.redis.hgetall(self._status_key(rca_run_id))
        if not data:
            return None
        # Redis returns bytes when decode_responses=False; normalize to strings for JSON
        return {k.decode(): v.decode() for k, v in data.items()}

    def clear_status(self, rca_run_id: str) -> None:
        """Clear status hash (cleanup)."""
        self.redis.delete(self._status_key(rca_run_id))
