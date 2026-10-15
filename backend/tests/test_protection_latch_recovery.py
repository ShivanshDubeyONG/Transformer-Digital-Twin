"""Protection-trip latch, authorized clearance, and OTHI recovery regressions.

Covers the lifecycle Trip -> OTHI 0 -> Acknowledged (still latched) -> Authorized resolution ->
healthy telemetry -> OTHI recovers, at engine level and through the public API as the UI drives it:
- only an authorized resolution of the protection advisory unlatches; ACK, normal frames, and
  resolutions of unrelated advisories never do;
- "after the trip" is ledger order, so a resolution stamped with the trailing twin watermark still counts;
- injected telemetry stamped outside the replay timeline (e.g. wall-clock) is rejected instead of
  pushing the watermark past every replay frame and freezing OTHI at 0;
- injected events never re-enter the dataset replay, and reset / asset switch isolate the latch.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.othi import (
    OTHIEngine,
    aggregate_othi_max_plus_secondary,
    aggregate_othi_v2,
    is_authorized_trip_resolution,
)
from app.main import create_app
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.health import HealthStatus
from app.models.maintenance import FeedbackAction, OperatorFeedbackEvent
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)

ASSET = "DT-01"
T0 = datetime(2025, 4, 19, 0, 0, tzinfo=timezone.utc)
CADENCE = timedelta(minutes=30)
PROT_REC_ID = f"REC-{ASSET}-MNT-PROT-001"


def _meas(signal_id: str, value: float | bool, unit: str = "1", flags: list[str] | None = None,
          severity: QualitySeverity = QualitySeverity.GOOD) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        value=value,
        value_type="bool" if isinstance(value, bool) else "float",
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=flags or []),
    )


def _event(idx: int, *, trip: bool = False) -> CanonicalEvent:
    meas = [
        _meas("top_oil_temperature", 55.0, "Cel"),
        _meas("ambient_temperature", 30.0, "Cel"),
        _meas("current_i1", 0.0 if trip else 120.0, "A"),
        _meas("current_i2", 0.0 if trip else 118.0, "A"),
        _meas("current_i3", 0.0 if trip else 121.0, "A"),
        _meas("voltage_v1", 0.0 if trip else 247.0, "V"),
        _meas("lv_breaker_closed", 0.0 if trip else 1.0),
    ]
    if trip:
        meas.append(_meas("oil_temp_trip_flag", True, flags=["DIRECT_TRIP"], severity=QualitySeverity.BAD))
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=f"evt-{idx}",
        asset_id=ASSET,
        event_time_utc=T0 + idx * CADENCE,
        source=SourceRef(system="test", adapter_id="test", source_record_id=f"r{idx}",
                         source_uri="test://latch", raw_sha256="0" * 64),
        measurements=meas,
        event_quality_flags=["PROTECTION_TRIP_ACTIVE"] if trip else [],
        mapping_version="1.0.0",
    )


def _feedback(fid: str, action: FeedbackAction, ts: datetime, *, rec_id: str = PROT_REC_ID,
              merge_key: str = "SAFETY_PROTECTION_TRIP", reason: str | None = None) -> OperatorFeedbackEvent:
    return OperatorFeedbackEvent(
        feedback_id=fid,
        asset_id=ASSET,
        timestamp_utc=ts,
        recommendation_id=rec_id,
        merge_key=merge_key,
        action=action,
        operator_id="op",
        actor_id="op",
        reason_code=reason,
        notes="test",
        rationale="test",
    )


# ---------------------------------------------------------------------------
# Engine-level lifecycle
# ---------------------------------------------------------------------------


def test_trip_ack_resolve_recover_sequence():
    """Trip -> 0, ACK and normal frames keep it latched, authorized resolution -> recovery > 0."""
    ledger = OperatorFeedbackLedger()
    engine = OTHIEngine(expected_cadence_seconds=CADENCE.total_seconds())
    engine.feedback_ledger = ledger

    assert engine.evaluate(_event(0)).othi_score == 100

    tripped = engine.evaluate(_event(1, trip=True))
    assert tripped.othi_score == 0
    assert tripped.operational_status == HealthStatus.CRITICAL
    assert tripped.driving_condition_family == "DIRECT_PROTECTION_TRIP"

    # Acknowledgement is workflow-only: it never clears a genuine latched trip
    ledger.append(_feedback("fb-ack", FeedbackAction.ACKNOWLEDGE, T0 + CADENCE))
    for i in (2, 3):
        held = engine.evaluate(_event(i))
        assert held.othi_score == 0, "normal frames resuming must not clear the trip"
        assert engine.latched_protection_trip is True

    # Resolving an unrelated advisory, even with a documented code, does not clear the trip
    ledger.append(_feedback("fb-other", FeedbackAction.RESOLVE, T0 + 3 * CADENCE,
                            rec_id=f"REC-{ASSET}-MNT-SENS-006", merge_key="SENSOR_PLAUSIBILITY_FAULT",
                            reason="DOCUMENTED_RESOLUTION"))
    assert engine.evaluate(_event(4)).othi_score == 0

    # Authorized resolution stamped with the trailing watermark (earlier than the trip frame's
    # event time), as the API does when no explicit timestamp is sent. Ledger order decides.
    ledger.append(_feedback("fb-res", FeedbackAction.RESOLVE, T0 + CADENCE - timedelta(minutes=10),
                            reason="SITE_CLEARANCE_VERIFIED"))
    recovered = engine.evaluate(_event(5))
    assert engine.latched_protection_trip is False
    assert recovered.othi_score is not None and recovered.othi_score > 0
    assert recovered.driving_condition_family != "DIRECT_PROTECTION_TRIP"
    assert recovered.operational_status != HealthStatus.CRITICAL


def test_resolution_recorded_before_trip_does_not_clear_later_trip():
    ledger = OperatorFeedbackLedger()
    engine = OTHIEngine(expected_cadence_seconds=CADENCE.total_seconds())
    engine.feedback_ledger = ledger
    engine.evaluate(_event(0))
    # Stamped in the future relative to the trip, but recorded before it: must not count
    ledger.append(_feedback("fb-early", FeedbackAction.RESOLVE, T0 + 10 * CADENCE,
                            reason="SITE_CLEARANCE_VERIFIED"))
    assert engine.evaluate(_event(1, trip=True)).othi_score == 0
    assert engine.evaluate(_event(2)).othi_score == 0
    assert engine.latched_protection_trip is True


def test_trip_still_active_is_not_cleared_by_resolution():
    ledger = OperatorFeedbackLedger()
    engine = OTHIEngine(expected_cadence_seconds=CADENCE.total_seconds())
    engine.feedback_ledger = ledger
    engine.evaluate(_event(0, trip=True))
    ledger.append(_feedback("fb-res", FeedbackAction.RESOLVE, T0, reason="SITE_CLEARANCE_VERIFIED"))
    # Breaker still open / trip contact still asserted on the next frame: remains latched
    assert engine.evaluate(_event(1, trip=True)).othi_score == 0
    assert engine.latched_protection_trip is True


def test_non_protection_critical_anomaly_never_latches_zero():
    engine = OTHIEngine(expected_cadence_seconds=CADENCE.total_seconds())
    severe = EvidenceItem(
        evidence_id="ev-thermal-crit",
        asset_id=ASSET,
        event_time_utc=T0 + CADENCE,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
        observed_value=99.0,
        severity=1.0,
        confidence=1.0,
    )
    engine.evaluate(_event(0))
    assert engine.evaluate(_event(1), evidence_items=[severe]).raw_othi == 0
    assert engine.latched_protection_trip is False
    cleared = engine.evaluate(_event(2))
    assert cleared.othi_score == 100 and cleared.raw_othi == 100


@pytest.mark.parametrize(
    ("action", "reason", "rec_id", "merge_key", "expected"),
    [
        ("RESOLVE", "SITE_CLEARANCE_VERIFIED", PROT_REC_ID, None, True),
        ("DISMISS", "TRIP_RESOLVED_AND_RESET", None, "SAFETY_PROTECTION_TRIP", True),
        ("ACKNOWLEDGE", "SITE_CLEARANCE_VERIFIED", PROT_REC_ID, None, False),
        ("RESOLVE", None, PROT_REC_ID, None, False),
        ("RESOLVE", "OPERATOR_VERIFIED", PROT_REC_ID, None, False),
        ("RESOLVE", "DOCUMENTED_RESOLUTION", f"REC-{ASSET}-MNT-OIL-008", "OIL_LEVEL_LOSS_TREND", False),
    ],
)
def test_authorized_trip_resolution_predicate(action, reason, rec_id, merge_key, expected):
    assert is_authorized_trip_resolution(action, reason, rec_id, merge_key) is expected


@pytest.mark.parametrize("aggregate", [aggregate_othi_max_plus_secondary, aggregate_othi_v2])
def test_aggregation_bounds_monotonicity_and_trip_precedence(aggregate):
    rng = random.Random(20261011)
    domains = ["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"]
    for _ in range(500):
        sev = {d: rng.random() for d in rng.sample(domains, rng.randint(1, 5))}
        score = aggregate(sev)[0]
        assert 0 <= score <= 100
        worse = dict(sev)
        d = rng.choice(list(worse))
        worse[d] = min(1.0, worse[d] + rng.random() * 0.5)
        assert aggregate(worse)[0] <= score
        assert aggregate({**sev, "oil_protection": 1.0})[0] == 0


def test_runtime_reducer_uses_othi_v2():
    from app.api.deps import build_runtime_reducer

    reducer = build_runtime_reducer(settings=Settings(db_path=":memory:"), asset_id=ASSET)
    assert reducer.othi_engine.algorithm_version == "OTHI_V2"


@pytest.mark.parametrize("detector_id", ["DET_THERMAL_CUSUM_DRIFT", "DET_OIL_LEVEL_DECLINING_TREND"])
def test_shadow_detectors_do_not_penalize_othi(detector_id):
    engine = OTHIEngine(expected_cadence_seconds=CADENCE.total_seconds(), algorithm_version="OTHI_V2")
    shadow = EvidenceItem(
        evidence_id=f"ev-{detector_id}",
        asset_id=ASSET,
        event_time_utc=T0,
        category=AnomalyCategory.THERMAL_DEVIATION if "THERMAL" in detector_id else AnomalyCategory.PROTECTION_OR_OIL_STATUS,
        detector_id=detector_id,
        observed_value=1.0,
        severity=0.75,
        confidence=0.85,
    )
    bundle = engine.evaluate(_event(0), evidence_items=[shadow])
    assert bundle.othi_score == 100 and bundle.raw_othi == 100


def test_contact_from_bad_quality_frame_does_not_latch_trip():
    engine = OTHIEngine(expected_cadence_seconds=CADENCE.total_seconds())
    engine.evaluate(_event(0))
    comm_loss = _event(1).model_copy(update={"measurements": [
        _meas("lv_breaker_closed", 0.0, flags=["COMM_LOSS"], severity=QualitySeverity.BAD),
        _meas("lv_breaker_trip", 1.0, flags=["COMM_LOSS"], severity=QualitySeverity.BAD),
        _meas("top_oil_temperature", 55.0, "Cel"),
        _meas("current_i1", 120.0, "A"),
    ]})
    engine.evaluate(comm_loss)
    assert engine.latched_protection_trip is False


# ---------------------------------------------------------------------------
# API lifecycle as driven by the UI
# ---------------------------------------------------------------------------

API_ASSET = "DT-03"


@pytest.fixture
def client():
    app = create_app(settings=Settings(default_asset_id=API_ASSET, db_path=":memory:", environment="test"))
    with TestClient(app) as test_client:
        yield test_client


def _replay(c: TestClient, action: str, asset: str = API_ASSET, **kw) -> dict:
    res = c.post("/v1/replay", json={"action": action, "asset_id": asset, **kw})
    assert res.status_code == 200, res.text
    return res.json()


def _health(c: TestClient, asset: str = API_ASSET) -> dict:
    return c.get(f"/v1/assets/{asset}/state").json()["fact_bundle"]["health"]


def _watermark(c: TestClient, asset: str = API_ASSET) -> datetime:
    raw_ts = c.get(f"/v1/assets/{asset}/state").json()["twin_state"]["event_time_watermark_utc"]
    return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))


def _ui_trip(t: datetime, asset: str = API_ASSET) -> dict:
    """The protection-trip event the UI injects."""
    ev = _event(0, trip=True).model_copy(update={"asset_id": asset, "event_id": f"evt-trip-{t:%H%M}", "event_time_utc": t})
    return {"asset_id": asset, "events": [ev.model_dump(mode="json")]}


def _prot_rec(c: TestClient, asset: str = API_ASSET) -> dict | None:
    recs = c.get(f"/v1/assets/{asset}/recommendations").json()
    return next((r for r in recs if r["rule_id"] == "MNT-PROT-001"), None)


def _submit(c: TestClient, rec: dict, action: str, reason: str | None = None) -> None:
    res = c.post("/v1/feedback", json={
        "asset_id": API_ASSET, "action": action, "recommendation_id": rec["recommendation_id"],
        "merge_key": rec["merge_key"], "operator_id": "op", "reason_code": reason,
        "notes": "test", "rationale": "test",
    })
    assert res.status_code == 200, res.text


def test_api_trip_ack_resolve_recovery(client: TestClient):
    total = _replay(client, "start")["total_events"]
    _replay(client, "step", batch_size=4)
    assert _health(client)["othi_score"] > 0

    # UI stamps the trip one cadence after the twin watermark
    res = client.post("/v1/telemetry", json=_ui_trip(_watermark(client) + CADENCE))
    assert res.status_code == 201, res.text
    h = _health(client)
    assert h["othi_score"] == 0 and h["operational_status"] == "CRITICAL"
    rec = _prot_rec(client)
    assert rec is not None and rec["priority"] == "P0"

    _submit(client, rec, "ACKNOWLEDGE")
    _replay(client, "step", batch_size=2)
    assert _health(client)["othi_score"] == 0
    assert _prot_rec(client)["acknowledged"] is True

    _submit(client, rec, "RESOLVE", "SITE_CLEARANCE_VERIFIED")
    _replay(client, "step", batch_size=2)
    h = _health(client)
    assert h["othi_score"] is not None and h["othi_score"] > 0
    assert h["driving_condition_family"] != "DIRECT_PROTECTION_TRIP"
    assert h["operational_status"] != "CRITICAL"

    # The injected trip is stored for audit but never becomes part of the dataset replay
    _replay(client, "reset", asset="DT-01")
    assert _replay(client, "start")["total_events"] == total


def test_api_rejects_injection_outside_replay_timeline(client: TestClient):
    # Before the replay has started, nothing anchors the event: rejected, and the dataset still loads
    assert client.post("/v1/telemetry", json=_ui_trip(T0 + 5 * CADENCE)).status_code == 422
    total = _replay(client, "start")["total_events"]
    assert total > 1
    _replay(client, "step", batch_size=4)
    wm = _watermark(client)

    # Wall-clock stamped injection would freeze the twin behind the watermark: rejected
    wall_clock = datetime(2026, 10, 11, 10, 0, tzinfo=timezone.utc)
    assert client.post("/v1/telemetry", json=_ui_trip(wall_clock)).status_code == 422
    assert _watermark(client) == wm

    _replay(client, "step", batch_size=2)
    assert _watermark(client) > wm
    assert _health(client)["othi_score"] > 0


def test_api_reset_and_asset_switch_isolate_latched_trip(client: TestClient):
    _replay(client, "start")
    _replay(client, "step", batch_size=4)
    assert client.post("/v1/telemetry", json=_ui_trip(_watermark(client) + CADENCE)).status_code == 201
    assert _health(client)["othi_score"] == 0

    # Asset switch: the other asset starts clean
    _replay(client, "start", asset="DT-04")
    _replay(client, "step", asset="DT-04", batch_size=3)
    assert _health(client, "DT-04")["driving_condition_family"] != "DIRECT_PROTECTION_TRIP"

    # Back and reset: the unresolved latch from the previous run does not carry over
    _replay(client, "reset")
    _replay(client, "start")
    _replay(client, "step", batch_size=6)
    h = _health(client)
    assert h["othi_score"] is not None and h["othi_score"] > 0
    assert h["driving_condition_family"] != "DIRECT_PROTECTION_TRIP"
