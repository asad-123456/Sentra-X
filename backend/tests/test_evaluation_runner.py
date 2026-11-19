"""FR-10 evaluation runner: AC-6 (0% bypass) and AC-18 (reports, no production rows written)."""
import csv
import io

import pytest

from app.services.evaluation_runner import EvaluationRunner, compute_metrics
from app.services import evaluation_runner
from app.services.llm_adapter import MockAdapter
from app.worker.worker_settings import get_worker_settings


@pytest.fixture(autouse=True)
def _mock_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_worker_settings.cache_clear()
    EvaluationRunner._cached_report = None
    yield
    get_worker_settings.cache_clear()
    EvaluationRunner._cached_report = None


def _row(group, expected_verdict, expected_severity, verdict, severity, floor=False):
    return {"group": group, "expected_verdict": expected_verdict,
            "expected_severity": expected_severity, "verdict": verdict,
            "severity": severity, "floor": floor, "latency_ms": 10}


def test_suite_has_30_payloads_10_per_category_and_no_canned_results():
    suite = EvaluationRunner.load_suite()
    assert len(suite) == 30
    assert {c: [i["category"][0] for i in suite].count(c) for c in "123"} == {"1": 10, "2": 10, "3": 10}
    assert all(set(i) == {"id", "category", "target_field", "payload"} for i in suite)


def test_metric_arithmetic():
    acc = [
        _row("TP", "TRUE_POSITIVE", "HIGH", "TRUE_POSITIVE", "HIGH"),
        _row("TP", "TRUE_POSITIVE", "CRITICAL", "FALSE_POSITIVE", "LOW"),
        _row("FP", "FALSE_POSITIVE", "LOW", "TRUE_POSITIVE", "MEDIUM"),
        _row("INCOMPLETE", "NEEDS_ANALYST_REVIEW", "MEDIUM", "NEEDS_ANALYST_REVIEW", "MEDIUM", True),
        _row("INCOMPLETE", "NEEDS_ANALYST_REVIEW", "MEDIUM", "TRUE_POSITIVE", "HIGH"),
    ]
    inj = [{"bypassed": True, "floor": False, "latency_ms": 30},
           {"bypassed": False, "floor": True, "latency_ms": 30}]
    m = compute_metrics(acc, inj, guardrails=True)
    assert m["precision"] == pytest.approx(0.5)
    assert m["recall"] == pytest.approx(0.5)
    assert m["f1"] == pytest.approx(0.5)
    assert m["false_negative_rate_high_critical"] == pytest.approx(0.5)
    assert m["abstention_accuracy"] == pytest.approx(0.5)
    assert m["injection_success_rate"] == pytest.approx(0.5)
    assert m["safety_floor_trigger_rate"] == pytest.approx(2 / 7)
    assert m["mean_latency_ms"] == pytest.approx(110 / 7)
    assert compute_metrics(acc, inj, guardrails=False)["safety_floor_trigger_rate"] is None


def test_report_has_every_fr10_metric_for_both_modes():
    rep = EvaluationRunner.run()
    assert rep["is_dry_run"] is True and "DRY RUN" in rep["notice"]
    names = " | ".join(m["metric_name"] for m in rep["comparative_metrics"])
    for word in ("Precision", "Recall", "F1", "False-Negative", "Abstention",
                 "Safety Floor", "Latency", "Bypass"):
        assert word in names
    assert set(rep["metrics"]) == {"baseline", "sentrax"}
    assert rep["total_payloads"] == 30


def test_no_payload_bypasses_the_full_pipeline():  # AC-6
    rep = EvaluationRunner.run()
    assert [p["id"] for p in rep["adversarial_suite"] if p["sentrax_bypassed"]] == []
    assert rep["sentrax_bypass_rate"] == 0.0 and rep["nfr3_target_achieved"] is True


def test_the_unguarded_baseline_is_fooled_by_at_least_one_payload():
    assert EvaluationRunner.run()["baseline_bypass_rate"] > 0


def test_exports_carry_the_notice_and_all_payloads():
    rep = EvaluationRunner.run()
    md, csv_text = EvaluationRunner.to_markdown(rep), EvaluationRunner.to_csv(rep)
    assert "DRY RUN" in md and "PI-01" in md and "PI-30" in md
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 30
    assert rows[0]["Provider"] == "mock" and rows[0]["Dry Run"] == "TRUE"


def test_failed_provider_is_inconclusive(monkeypatch):
    monkeypatch.setattr(
        evaluation_runner, "_make_adapter", lambda: MockAdapter(failure_mode="http_400")
    )
    report = EvaluationRunner.run()
    assert report["metrics"]["sentrax"]["errors"] == 60
    assert report["sentrax_bypass_rate"] is None
    assert report["result"] == "inconclusive"
    assert report["nfr3_target_achieved"] is False
    assert all(not metric["is_target_met"] for metric in report["comparative_metrics"])


def test_report_and_export_reads_do_not_start_evaluation(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers.admin import verify_admin_access

    def unexpected_adapter():
        pytest.fail("A read tried to start an evaluation")

    monkeypatch.setattr(evaluation_runner, "_make_adapter", unexpected_adapter)
    monkeypatch.setitem(app.dependency_overrides, verify_admin_access, lambda: None)
    client = TestClient(app)
    report = client.get("/api/v1/evaluation/report")
    assert report.status_code == 200 and report.json() is None
    for export in ("export-md", "export-csv"):
        assert client.get(f"/api/v1/evaluation/{export}").status_code == 404


def test_run_adds_no_rows_to_production_tables():  # AC-18
    from sqlalchemy import text
    from app.database import SyncSessionLocal

    tables = ("analyst_decisions_audit", "ai_assessments", "evidence_packs", "alerts")

    def counts():
        with SyncSessionLocal() as s:
            return {t: s.execute(text(f"SELECT count(*) FROM {t}")).scalar_one() for t in tables}

    try:
        before = counts()
    except Exception as exc:
        pytest.skip(f"database not reachable ({type(exc).__name__})")
    EvaluationRunner.run()
    assert counts() == before
