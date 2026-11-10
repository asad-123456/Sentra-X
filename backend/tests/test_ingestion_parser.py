import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.ingestion.batch import next_cursor, process_batch
from app.ingestion.parser import (
    extract_process_signature,
    normalize_signature,
    parse_alert,
    parse_timestamp,
)

SAMPLES = Path(__file__).parent / "fixtures" / "wazuh_samples"


def make_alert(i=1, level=5, **over):
    a = {
        "id": f"1730000000.{i:05d}",
        "timestamp": "2026-10-22T10:15:30.123+0000",
        "rule": {"id": "5710", "level": level, "description": "sshd: attempt to login"},
        "agent": {"id": "001", "name": "ubuntu-1", "ip": "10.0.0.11"},
        "data": {"srcip": "203.0.113.9"},
        "decoder": {"name": "sshd"},
        "full_log": "Failed password for invalid user x",
    }
    a.update(over)
    return a


# ---- timestamps ----
def test_timestamp_utc_no_colon_offset():
    assert parse_timestamp("2026-10-22T10:15:30.123+0000") == datetime(
        2026, 10, 22, 10, 15, 30, 123000, tzinfo=timezone.utc
    )


def test_timestamp_converts_to_utc():
    assert parse_timestamp("2026-10-22T10:15:30+0500").hour == 5


def test_timestamp_garbage_raises():
    with pytest.raises(ValueError):
        parse_timestamp("yesterday")


# ---- process signature ----
def test_signature_windows_image_normalized():
    raw = {"data": {"win": {"eventdata": {"image": "  C:\\Windows\\System32\\CMD.exe "}}},
           "decoder": {"name": "sshd"}}
    assert extract_process_signature(raw) == "c:/windows/system32/cmd.exe"


def test_signature_falls_back_to_syscheck_then_decoder():
    assert extract_process_signature({"syscheck": {"path": "/Root/FimTest/a.txt"},
                                      "decoder": {"name": "syscheck"}}) == "/root/fimtest/a.txt"
    assert extract_process_signature({"decoder": {"name": "sshd"}}) == "sshd"


def test_signature_empty_value_falls_through_and_none_when_absent():
    assert extract_process_signature({"syscheck": {"path": "   "}, "decoder": {"name": "sudo"}}) == "sudo"
    assert extract_process_signature({}) is None


def test_signature_capped_at_512():
    assert len(normalize_signature("A" * 600)) == 512


# ---- parse_alert ----
def test_accepts_level_4_and_extracts_fields():
    out = parse_alert(make_alert(level=4))
    assert out.status == "accepted"
    a = out.alert
    assert a.rule_id == "5710" and a.rule_level == 4
    assert a.agent_id == "001" and a.src_ip == "203.0.113.9"
    assert a.process_signature == "sshd"
    assert a.alert_timestamp.tzinfo is not None


def test_noise_below_threshold():
    assert parse_alert(make_alert(level=3)).status == "noise"


@pytest.mark.parametrize("level", [16, -1, None, "abc"])
def test_invalid_level(level):
    assert parse_alert(make_alert(level=level)).status == "invalid"


def test_level_as_string_is_accepted():
    out = parse_alert(make_alert(level="7"))
    assert out.status == "accepted" and out.alert.rule_level == 7


def test_missing_required_fields_are_invalid():
    for key in ("id", "timestamp", "agent"):
        raw = make_alert()
        del raw[key]
        assert parse_alert(raw).status == "invalid", key


def test_bad_or_missing_srcip_is_none():
    assert parse_alert(make_alert(data={"srcip": "not-an-ip"})).alert.src_ip is None
    assert parse_alert(make_alert(data={})).alert.src_ip is None


def test_raw_payload_is_untouched():
    raw = make_alert()
    before = copy.deepcopy(raw)
    out = parse_alert(raw)
    assert raw == before
    assert out.alert.raw_payload == before


def test_non_dict_input_does_not_crash():
    assert parse_alert("garbage").status == "invalid"
    assert parse_alert(None).status == "invalid"


# ---- batch (mirrors AC-1) ----
def test_batch_100_alerts_gives_70():
    good = [make_alert(i, level=5) for i in range(70)]
    noise = [make_alert(1000 + i, level=2) for i in range(20)]
    repeats = [copy.deepcopy(good[i]) for i in range(10)]
    res = process_batch(good + noise + repeats)
    assert len(res.alerts) == 70
    s = res.stats
    assert (s.received, s.noise, s.duplicate_in_batch, s.accepted) == (100, 20, 10, 70)


# ---- cursor ----
def test_cursor_overlap():
    t = datetime(2026, 10, 22, 10, 0, 0, tzinfo=timezone.utc)
    assert next_cursor(t) == t - timedelta(seconds=60)
    assert next_cursor(None) is None


# ---- real samples from Part 2 ----
def test_real_samples_parse():
    files = sorted(SAMPLES.glob("*.json"))
    if not files:
        pytest.skip("no sample fixtures found")
    for f in files:
        raw = json.loads(f.read_text(encoding="utf-8"))
        out = parse_alert(raw)
        assert out.status in ("accepted", "noise"), f"{f.name}: {out.reason}"
        if out.status == "accepted":
            assert out.alert.alert_timestamp.utcoffset() == timedelta(0)
            assert out.alert.raw_payload == raw