from datetime import datetime, timedelta, timezone

import pytest

from app.services.evidence_assembler import AlertRecord, CorrelatedAlert, select_correlated

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def _alert(agent="001", ip=None):
    return AlertRecord(
        wazuh_alert_id="A-0", alert_timestamp=T0, rule_id="5710", rule_level=5,
        rule_description="d", agent_id=agent, agent_name="host", src_ip=ip,
    )


def _cand(agent="002", ip=None, wid="C-1"):
    return CorrelatedAlert(
        wazuh_alert_id=wid, alert_timestamp=T0 - timedelta(minutes=5),
        rule_id="5710", rule_level=5, rule_description="d", agent_id=agent, src_ip=ip,
    )


@pytest.mark.parametrize("ip", ["127.0.0.1", "::1", "0.0.0.0", "::ffff:127.0.0.1"])
def test_shared_loopback_ip_does_not_correlate_different_agents(ip):
    assert select_correlated(_alert(ip=ip), [_cand(ip=ip)]) == []


def test_loopback_alert_still_correlates_on_same_agent():
    out = select_correlated(_alert(agent="001", ip="127.0.0.1"), [_cand(agent="001", ip="127.0.0.1")])
    assert len(out) == 1


def test_shared_public_ip_still_correlates_different_agents():
    out = select_correlated(_alert(ip="203.0.113.9"), [_cand(ip="203.0.113.9")])
    assert len(out) == 1