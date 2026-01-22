"""模块说明：RQ Worker 启动入口。"""

import logging

import redis
from rq import Worker, Queue, Connection

from api.config import settings

logger = logging.getLogger("automation_hub.worker")


def _get_queue_names() -> list[str]:
    return [name.strip() for name in settings.QUEUE_NAME.split(",") if name.strip()]


redis_conn = redis.from_url(settings.REDIS_URL)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    queues = _get_queue_names()
    logger.info("Starting worker for queues: %s", ", ".join(queues))
    with Connection(redis_conn):
        worker = Worker([Queue(name) for name in queues])
        worker.work(with_scheduler=True)