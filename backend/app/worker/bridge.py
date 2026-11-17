"""The pipeline step of the worker: Abdur's code, called in the order his modules were written for.

    assemble_evidence_pack  ->  triage_alert (blocking, owns its 3 retries)  ->  apply_guardrails

Nothing in here touches the database. The processor loads everything first and saves everything afterwards, so no
DB connection is held during the 2 to 6 second model call."""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Optional

from app.config import settings
from app.services.evidence_assembler import (AlertRecord, CorrelatedAlert, EvidencePack,
                                             assemble_evidence_pack)
from app.services.llm_adapter import (InjectedExemplar, LLMAdapter, MockAdapter,
                                      TriageCallResult, get_adapter, triage_alert)
from app.services.rules_engine import GuardrailResult, apply_guardrails
from app.worker.worker_settings import get_worker_settings

log = logging.getLogger("sentrax.worker")


@dataclass
class Context:
    """Everything the pipeline needs, loaded in one short transaction (plain objects, no ORM)."""
    record: AlertRecord
    tier: str
    correlated: list[CorrelatedAlert]
    exemplars: list[InjectedExemplar]


@dataclass
class TriageOutcome:
    pack: Optional[EvidencePack]            # None if the pack could not be built
    result: Optional[TriageCallResult]      # None if the call never happened
    guardrail: Optional[GuardrailResult]    # None means the triage FAILED
    provider: str
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.guardrail is not None


class DelayedAdapter(LLMAdapter):
    """Mock model with simulated latency, for the AC-19 / AC-22 load test."""
    provider = "mock"

    def __init__(self, inner: LLMAdapter, low: float, high: float):
        self.inner, self.low, self.high = inner, low, high
        self.model_name = inner.model_name

    def generate(self, system_prompt: str, user_prompt: str, timeout_s: float) -> str:
        time.sleep(random.uniform(self.low, self.high))
        return self.inner.generate(system_prompt, user_prompt, timeout_s)


def provider_of(adapter: LLMAdapter) -> str:
    return (getattr(adapter, "provider", None)
            or type(adapter).__name__.replace("Adapter", "").lower() or "unknown")[:32]


def build_adapter() -> LLMAdapter:
    """The adapter named by LLM_PROVIDER (mock | gemini | claude). Raises if it cannot be built, for example a
    missing API key, so the caller can refuse to start the worker instead of failing every alert."""
    adapter = get_adapter(settings.LLM_PROVIDER)
    w = get_worker_settings()
    if isinstance(adapter, MockAdapter) and w.MOCK_DELAY_MAX_SECONDS > 0:
        adapter = DelayedAdapter(adapter, w.MOCK_DELAY_MIN_SECONDS, w.MOCK_DELAY_MAX_SECONDS)
    return adapter


def run_pipeline(ctx: Context, adapter: LLMAdapter) -> TriageOutcome:
    """Never raises. A failed triage comes back with guardrail=None."""
    provider = provider_of(adapter)
    pack = result = None
    try:
        pack = assemble_evidence_pack(ctx.record, ctx.tier, ctx.correlated, [e.id for e in ctx.exemplars])
        result = triage_alert(pack, adapter, ctx.exemplars)       # blocks; 1 attempt + up to 3 retries
        if not result.succeeded or result.output is None:
            return TriageOutcome(pack, result, None, provider, result.last_error or "triage failed")
        # Guardrails run on the model's ORIGINAL output.
        guardrail = apply_guardrails(ctx.record.rule_level, result.output, pack.valid_dot_keys,
                                     pack.injection_suspect)
        return TriageOutcome(pack, result, guardrail, provider)
    except Exception as exc:
        log.exception("pipeline crashed for alert %s", ctx.record.wazuh_alert_id)
        return TriageOutcome(pack, result, None, provider, f"{type(exc).__name__}: {exc}")
