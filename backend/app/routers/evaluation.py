from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query, Response

from ..services.evaluation_runner import EvaluationRunner
from .admin import verify_admin_access

router = APIRouter(prefix="/evaluation", tags=["Adversarial Evaluation & Benchmarking"])


@router.get("/suite", response_model=List[Dict[str, Any]])
def get_adversarial_suite(_: None = Depends(verify_admin_access)):
    """Admin-only: returns the adversarial benchmark suite (SDD §6.2)."""
    return EvaluationRunner.load_suite()


@router.get("/report", response_model=Dict[str, Any])
def get_evaluation_report(_: None = Depends(verify_admin_access)):
    """Admin-only: returns the latest evaluation report (SDD §6.2)."""
    return EvaluationRunner.get_latest_report()


@router.post("/run", response_model=Dict[str, Any])
def run_evaluation(mode: str = Query("full"), _: None = Depends(verify_admin_access)):
    """Admin-only: triggers an evaluation run (SDD §6.2)."""
    return EvaluationRunner.run(mode=mode)


@router.get("/export-md")
def export_evaluation_markdown(_: None = Depends(verify_admin_access)):
    """Admin-only: exports the evaluation report as Markdown (AC-18)."""
    md_content = EvaluationRunner.to_markdown()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        content=md_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=sentrax_adversarial_evaluation_{today_str}.md"},
    )


@router.get("/export-csv")
def export_evaluation_csv(_: None = Depends(verify_admin_access)):
    """Admin-only: exports the adversarial suite evaluation results as CSV (AC-18)."""
    csv_content = EvaluationRunner.to_csv()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sentrax_adversarial_evaluation_{today_str}.csv"},
    )
