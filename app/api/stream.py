import json
import asyncio
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse
from app.core.redis_clients import get_async_redis
from app.services.progress import ProgressService

router = APIRouter(prefix="/rca-runs", tags=["Stream"])


async def event_generator(rca_run_id: str):
    """Generate SSE events from Redis pub/sub."""
    redis = await get_async_redis()
    pubsub = redis.pubsub()
    channel = f"rca:{rca_run_id}"

    try:
        await pubsub.subscribe(channel)

        # Immediately send latest status snapshot
        progress_service = ProgressService()
        latest_status = progress_service.get_latest_status(rca_run_id)
        if latest_status:
            yield {"data": json.dumps(latest_status)}

        # Listen for new events
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield {"data": message["data"]}

                # Stop streaming if done or error
                try:
                    event_data = json.loads(message["data"])
                    if event_data.get("status") in ["done", "error"]:
                        break
                except json.JSONDecodeError:
                    pass

    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


@router.get("/{rca_run_id}/stream")
async def stream_rca_progress(rca_run_id: str):
    """Stream RCA progress via SSE."""
    return EventSourceResponse(event_generator(rca_run_id))
