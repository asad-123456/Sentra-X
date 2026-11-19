import queue
import uuid


class TriageQueue(queue.Queue[uuid.UUID]):
    """Unbounded FIFO that holds each waiting alert ID once."""

    def __init__(self) -> None:
        super().__init__()
        self._queued: set[uuid.UUID] = set()

    def enqueue(self, alert_id: uuid.UUID) -> bool:
        with self.not_empty:
            if alert_id in self._queued:
                return False
            self._put(alert_id)
            self.unfinished_tasks += 1
            self.not_empty.notify()
            return True

    def _put(self, alert_id: uuid.UUID) -> None:
        super()._put(alert_id)
        self._queued.add(alert_id)

    def _get(self) -> uuid.UUID:
        alert_id = super()._get()
        self._queued.discard(alert_id)
        return alert_id


# PostgreSQL retains pending rows if this process exits before consuming them.
triage_queue = TriageQueue()


def enqueue_triage(alert_id: uuid.UUID) -> None:
    triage_queue.enqueue(alert_id)
