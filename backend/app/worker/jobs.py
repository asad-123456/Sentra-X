import queue
import uuid

# NOTE: This is an in-process, in-memory queue. Alert IDs are lost if the process
# restarts between the DB commit and the worker consuming them. The alert stays in
# the DB with status=PENDING_REVIEW — Abdur's worker must handle recovery by
# scanning for PENDING_REVIEW alerts on startup.
triage_queue: "queue.Queue[uuid.UUID]" = queue.Queue()


def enqueue_triage(alert_id: uuid.UUID) -> None:
    triage_queue.put(alert_id)