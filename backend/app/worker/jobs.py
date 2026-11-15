import queue
import uuid

triage_queue: "queue.Queue[uuid.UUID]" = queue.Queue()


def enqueue_triage(alert_id: uuid.UUID) -> None:
    triage_queue.put(alert_id)
