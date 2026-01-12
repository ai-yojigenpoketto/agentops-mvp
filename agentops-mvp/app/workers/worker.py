#!/usr/bin/env python
"""RQ Worker for processing RCA jobs."""
import sys
from rq import Worker
from app.core.redis_clients import get_sync_redis
from app.core.settings import settings
from app.core.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    """Start RQ worker."""
    redis_conn = get_sync_redis()
    queues = [settings.rq_queue_name]

    logger.info(f"Starting RQ worker for queues: {queues}")
    worker = Worker(queues, connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Worker interrupted, shutting down")
        sys.exit(0)
