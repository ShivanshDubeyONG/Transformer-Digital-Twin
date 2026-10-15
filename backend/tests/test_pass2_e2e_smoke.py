"""Pass 2 End-to-End Integration and Demo Smoke Tests.

Validates the full operator lifecycle via public FastAPI endpoints:
1. Replay startup, stepping, and telemetry/state/health consistency.
2. Protection trip injection, immediate P0 MNT-PROT-001 advisory and OTHI=0 override.
3. Operator ACKNOWLEDGE persistence across subsequent replay steps.
4. Operator RESOLVE ("SITE_CLEARANCE_VERIFIED") unlatching and OTHI recovery.
5. Replay reset clean state isolation.
6. Asset switching (DT-01 -> TX_1000_COMM) with complete boundary isolation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_measurement(
    signal_id: str,
    value: float | bool,
    unit: str = "A",
    phase: str | None = None,
    flags: list[str] | None = None,
) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        phase=phase,
        value=value,
        value_type="bool" if isinstance(value, bool) else "float",
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(
            severity=QualitySeverity.GOOD,
            flags=flags or [],
        ),
    )


def _make_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-01",
    is_trip: bool = False,
    i_l1: float = 100.0,
    top_oil: float = 65.0,
) -> CanonicalEvent:
    meas = [
        _make_measurement("current_l1", i_l1, "A", phase="L1"),
        _make_measurement("current_l2", i_l1, "A", phase="L2"),
        _make_measurement("current_l3", i_l1, "A", phase="L3"),
        _make_measurement("top_oil_temperature", top_oil, "Cel"),
        _make_measurement("ambient_temperature", 30.0, "Cel"),
    ]
    if is_trip:
        meas.append(_make_measurement("oil_temp_trip_flag", True, unit="1", flags=["DIRECT_TRIP"]))

    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        source=SourceRef(
            system="test",
            adapter_id="test_adapter",
            source_record_id=event_id,
            source_uri="test://events",
            raw_sha256="0" * 64,
        ),
        measurements=meas,
        event_quality_flags=["PROTECTION_TRIP_ACTIVE"] if is_trip else [],
        mapping_version="1.0.0",
    )


@pytest.fixture
def client() -> TestClient:
    test_settings = Settings(
        app_name="Digital Twin E2E Smoke Test",
        app_version="1.0.0-smoke",
        api_v1_prefix="/v1",
        environment="test",
        default_asset_id="DT-01",
        db_path=":memory:",
    )
    app = create_app(settings=test_settings)
    with TestClient(app) as test_client:
        yield test_client


def test_e2e_full_operator_lifecycle_and_trip_unlatch(client: TestClient):
    """End-to-end validation of replay, state, trip, ACK, RESOLVE, and reset."""
    # 1. Verify Assets endpoint
    res_assets = client.get("/v1/assets")
    assert res_assets.status_code == 200
    assets_data = res_assets.json()
    assert assets_data["active_asset_id"] == "DT-01"

    # 2. Start replay on DT-01
    res_start = client.post("/v1/replay", json={"action": "start", "asset_id": "DT-01"})
    assert res_start.status_code == 200
    start_data = res_start.json()
    assert start_data["status"] == "running"
    assert start_data["total_events"] > 0

    # 3. Step replay forward by 3 steps
    res_step = client.post("/v1/replay", json={"action": "step", "batch_size": 3, "asset_id": "DT-01"})
    assert res_step.status_code == 200
    step_data = res_step.json()
    assert step_data["processed_events"] == 3

    # 4. Check asset state and health consistency
    res_state = client.get("/v1/assets/DT-01/state")
    assert res_state.status_code == 200
    state_data = res_state.json()
    assert state_data["twin_state"] is not None
    assert state_data["fact_bundle"] is not None
    fb = state_data["fact_bundle"]
    assert fb["health"]["othi_score"] is not None
    assert fb["health"]["raw_othi"] is not None
    assert fb["health"]["othi_score"] >= 0

    # 5. Inject direct protection trip at t_trip
    curr_time_str = fb["health"]["timestamp_utc"]
    curr_time = datetime.fromisoformat(curr_time_str.replace("Z", "+00:00"))
    t_trip = curr_time + timedelta(minutes=15)
    trip_event = _make_event("trip-ev-001", t_trip, asset_id="DT-01", is_trip=True)

    res_telemetry = client.post("/v1/telemetry", json={"event": trip_event.model_dump(mode="json")})
    assert res_telemetry.status_code == 201

    # 6. Verify health dropped to 0 and DIRECT_PROTECTION_TRIP driving condition
    res_health = client.get("/v1/assets/DT-01/health")
    assert res_health.status_code == 200
    health_data = res_health.json()
    assert health_data["othi_score"] == 0
    assert health_data["driving_condition_family"] == "DIRECT_PROTECTION_TRIP"
    assert health_data["operational_status"] == "CRITICAL"

    # 7. Verify P0 advisory MNT-PROT-001 is present
    res_rec = client.get("/v1/assets/DT-01/recommendations")
    assert res_rec.status_code == 200
    recs = res_rec.json()
    prot_rec = next((r for r in recs if "PROT" in r["rule_id"] or "PROT" in r["recommendation_id"]), None)
    assert prot_rec is not None
    assert prot_rec["priority"] == "P0"
    rec_id = prot_rec["recommendation_id"]

    # 8. Operator acknowledges advisory
    t_ack = t_trip + timedelta(minutes=5)
    res_fb_ack = client.post(
        "/v1/feedback",
        json={
            "asset_id": "DT-01",
            "action": "ACKNOWLEDGE",
            "recommendation_id": rec_id,
            "operator_id": "operator_chief",
            "timestamp_utc": t_ack.isoformat(),
            "notes": "Control room acknowledged trip.",
        },
    )
    assert res_fb_ack.status_code == 200

    # Verify recommendation transitioned to acknowledged
    res_rec_ack = client.get("/v1/assets/DT-01/recommendations")
    recs_ack = res_rec_ack.json()
    prot_rec_ack = next(r for r in recs_ack if r["recommendation_id"] == rec_id)
    assert prot_rec_ack["acknowledged"] is True

    # 9. Step forward with normal event before resolution: trip remains latched!
    t_interim = t_trip + timedelta(minutes=10)
    normal_interim = _make_event("norm-interim-001", t_interim, asset_id="DT-01", is_trip=False)
    client.post("/v1/telemetry", json={"event": normal_interim.model_dump(mode="json")})

    res_health_interim = client.get("/v1/assets/DT-01/health")
    assert res_health_interim.json()["othi_score"] == 0

    # 10. Operator submits authorized RESOLVE
    t_resolve = t_trip + timedelta(minutes=30)
    res_fb_resolve = client.post(
        "/v1/feedback",
        json={
            "asset_id": "DT-01",
            "action": "RESOLVE",
            "recommendation_id": rec_id,
            "operator_id": "field_engineer",
            "reason_code": "SITE_CLEARANCE_VERIFIED",
            "timestamp_utc": t_resolve.isoformat(),
            "notes": "Field inspection cleared, breaker reset, safe to re-energize.",
        },
    )
    assert res_fb_resolve.status_code == 200

    # 11. Next normal event at t_post_res: trip unlatches and health recovers
    t_post_res = t_resolve + timedelta(minutes=15)
    normal_post = _make_event("norm-post-001", t_post_res, asset_id="DT-01", is_trip=False)
    client.post("/v1/telemetry", json={"event": normal_post.model_dump(mode="json")})

    res_health_recovered = client.get("/v1/assets/DT-01/health")
    h_rec = res_health_recovered.json()
    assert h_rec["othi_score"] is not None
    assert h_rec["othi_score"] > 50
    assert h_rec["driving_condition_family"] != "DIRECT_PROTECTION_TRIP"

    # 12. Replay Reset
    res_reset = client.post("/v1/replay", json={"action": "reset", "asset_id": "DT-01"})
    assert res_reset.status_code == 200
    reset_data = res_reset.json()
    assert reset_data["processed_events"] == 0
    assert reset_data["status"] == "reset"


def test_e2e_asset_switch_and_isolation(client: TestClient):
    """Switching assets (DT-01 -> TX_1000_COMM) maintains complete isolation."""
    # Start DT-01 and step
    client.post("/v1/replay", json={"action": "start", "asset_id": "DT-01"})
    client.post("/v1/replay", json={"action": "step", "batch_size": 2, "asset_id": "DT-01"})
    s_dt01 = client.get("/v1/assets/DT-01/state").json()
    assert s_dt01["twin_state"]["asset_id"] == "DT-01"

    # Switch to TX_1000_COMM
    res_tx = client.post("/v1/replay", json={"action": "start", "asset_id": "TX_1000_COMM"})
    assert res_tx.status_code == 200

    # Step TX_1000_COMM
    client.post("/v1/replay", json={"action": "step", "batch_size": 2, "asset_id": "TX_1000_COMM"})
    s_tx = client.get("/v1/assets/TX_1000_COMM/state").json()
    assert s_tx["twin_state"]["asset_id"] == "TX_1000_COMM"
    assert s_tx["fact_bundle"]["asset_id"] == "TX_1000_COMM"
    assert s_tx["fact_bundle"]["capabilities"]["highest_tier"] is not None
    assert s_tx["twin_state"]["open_episodes"] == []
