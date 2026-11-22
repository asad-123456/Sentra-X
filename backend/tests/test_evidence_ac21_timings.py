"""AC-21 evidence: a COPY of the benchmark in test_exemplars.py that prints max / mean / p95.

Run from backend/ with output visible:
    python -m pytest tests/test_evidence_ac21_timings.py -s -q
Reuses the fixtures of test_exemplars.py (database sentrax_test)."""
import random
import statistics
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.exemplars.service import find_exemplars
from app.exemplars.vocab import TIERS
from app.models.exemplar import FeedbackExemplar
from tests.test_exemplars import clean, factory  # noqa: F401  (fixtures)


def test_ac21_timings_printed(factory):  # noqa: F811
    rng = random.Random(7)
    rules, sigs = [f"R{i}" for i in range(20)], [f"proc{i}" for i in range(50)]
    now = datetime.now(timezone.utc)
    n = 10_000
    with factory.begin() as s:
        s.execute(FeedbackExemplar.__table__.insert(), [{
            "rule_id": rng.choice(rules),
            "process_signature": None if rng.random() < 0.1 else rng.choice(sigs),
            "asset_criticality": rng.choice(TIERS),
            "calibrated_verdict": "FALSE_POSITIVE", "calibrated_severity": "LOW",
            "rationale": "seeded exemplar for the lookup benchmark",
            "created_at": now - timedelta(minutes=i),
        } for i in range(n)])
        s.execute(text("ANALYZE feedback_exemplars"))
        loaded = s.execute(text("SELECT count(*) FROM feedback_exemplars")).scalar()

    def one():
        with factory.begin() as s:   # includes the hit-count UPDATE and the commit
            return find_exemplars(s, alert_id=uuid.uuid4(), rule_id=rng.choice(rules),
                                  process_signature=rng.choice(sigs), asset_criticality=rng.choice(TIERS))

    one()  # warm-up (not counted)
    times = []
    for _ in range(50):
        t0 = time.perf_counter()
        one()
        times.append((time.perf_counter() - t0) * 1000)
    times.sort()
    p95 = times[int(0.95 * (len(times) - 1))]
    print(f"\nAC-21: exemplars loaded={loaded}, lookups={len(times)}")
    print(f"AC-21: max={times[-1]:.2f} ms  mean={statistics.mean(times):.2f} ms  p95={p95:.2f} ms  min={times[0]:.2f} ms")
    assert loaded == n
    assert times[-1] < 50
