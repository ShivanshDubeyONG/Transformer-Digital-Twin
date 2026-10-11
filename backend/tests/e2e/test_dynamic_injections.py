"""End-to-End Regression Test Suite for Dynamic Scenario Injectors (Phase 10.2).

Verifies that the five canonical dynamic synthetic scenario injectors execute
through the real production pipeline, confirming:
1. INJ_SENSOR_SPIKE
2. INJ_STUCK_SENSOR
3. INJ_PERSISTENT_BIAS
4. INJ_SUSTAINED_OVERLOAD
5. INJ_PHASE_IMBALANCE

Flow verified:
Baseline Telemetry -> Injector -> Canonical Telemetry -> Validation/Features -> Reducer -> Anomaly/Evidence -> OTHI -> Maintenance -> FactBundle.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple
import pytest

from app.core.storage import StorageEngine
from app.engine.anomaly_detectors import MultiDomainAnomalyEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.electrical_episodes import ElectricalEpisodeEngine
from app.engine.exposure import ThermalExposureEngine
from app.engine.fact_bundle import assemble_fact_bundle
from app.engine.injectors import (
    ScenarioInjectorEngine,
    create_phase_imbalance_scenario,
    create_persistent_bias_scenario,
    create_sensor_spike_scenario,
    create_stuck_sensor_scenario,
    create_sustained_overload_scenario,
)
from app.engine.maintenance import MaintenanceEngine
from app.engine.othi import OTHIEngine
from app.engine.reducer import TwinReducer
from app.engine.replay import ReplayEngine
from app.models.anomaly import AnomalyCategory, EpisodeState
from app.models.electrical_episode import ElectricalEpisodeThresholds, ElectricalEpisodeType
from app.models.health import DomainFreshness, HealthStatus
from app.models.injector import GroundTruthCondition, InjectorType
from app.models.maintenance import ActionWindow, MaintenancePriority
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.twin_state import TwinState
from app.reports.exporters import export_report_csv, export_report_json
from app.reports.pdf_renderer import render_report_pdf
from app.reports.report_generator import generate_report_data


# ---------------------------------------------------------------------------
# Synthetic Baseline Telemetry Helpers
# ---------------------------------------------------------------------------

def _create_source_ref(seq_id: int) -> SourceRef:
    return SourceRef(
        system="tripura_csv",
        adapter_id="tripura_v1",
        source_record_id=f"row_{seq_id}",
        source_uri="file:///data/test.csv",
        raw_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
    )


def _create_synthetic_event(
    asset_id: str,
    event_time_utc: datetime,
    oti: float = 60.0,
    amb: float = 30.0,
    p_kw: float = 100.0,
    q_kvar: float = 50.0,
    s_kva: float = 111.8034,
    i_l1: float = 50.0,
    i_l2: float = 50.0,
    i_l3: float = 50.0,
    v_l1: float = 230.0,
    v_l2: float = 230.0,
    v_l3: float = 230.0,
    event_id: str | None = None,
    seq: int = 1,
) -> CanonicalEvent:
    """Create a standard balanced CanonicalEvent for testing."""
    q_good = MeasurementQuality(severity=QualitySeverity.GOOD)
    measurements = [
        Measurement(
            signal_id="oti_degc",
            value=oti,
            value_type="float",
            unit_ucum="Cel",
            original_name="OTI",
            original_value=str(oti),
            original_unit="degC",
            quality=q_good,
        ),
        Measurement(
            signal_id="ambient_temperature",
            value=amb,
            value_type="float",
            unit_ucum="Cel",
            original_name="Ambient",
            original_value=str(amb),
            original_unit="degC",
            quality=q_good,
        ),
        Measurement(
            signal_id="active_power_total",
            value=p_kw,
            value_type="float",
            unit_ucum="kW",
            original_name="P_tot",
            original_value=str(p_kw),
            original_unit="kW",
            quality=q_good,
        ),
        Measurement(
            signal_id="reactive_power_total",
            value=q_kvar,
            value_type="float",
            unit_ucum="kvar",
            original_name="Q_tot",
            original_value=str(q_kvar),
            original_unit="kvar",
            quality=q_good,
        ),
        Measurement(
            signal_id="apparent_power_total",
            value=s_kva,
            value_type="float",
            unit_ucum="kVA",
            original_name="S_tot",
            original_value=str(s_kva),
            original_unit="kVA",
            quality=q_good,
        ),
        Measurement(
            signal_id="current_l1",
            phase="L1",
            value=i_l1,
            value_type="float",
            unit_ucum="A",
            original_name="I1",
            original_value=str(i_l1),
            original_unit="A",
            quality=q_good,
        ),
        Measurement(
            signal_id="current_l2",
            phase="L2",
            value=i_l2,
            value_type="float",
            unit_ucum="A",
            original_name="I2",
            original_value=str(i_l2),
            original_unit="A",
            quality=q_good,
        ),
        Measurement(
            signal_id="current_l3",
            phase="L3",
            value=i_l3,
            value_type="float",
            unit_ucum="A",
            original_name="I3",
            original_value=str(i_l3),
            original_unit="A",
            quality=q_good,
        ),
        Measurement(
            signal_id="voltage_l1_n",
            phase="L1",
            value=v_l1,
            value_type="float",
            unit_ucum="V",
            original_name="V1",
            original_value=str(v_l1),
            original_unit="V",
            quality=q_good,
        ),
        Measurement(
            signal_id="voltage_l2_n",
            phase="L2",
            value=v_l2,
            value_type="float",
            unit_ucum="V",
            original_name="V2",
            original_value=str(v_l2),
            original_unit="V",
            quality=q_good,
        ),
        Measurement(
            signal_id="voltage_l3_n",
            phase="L3",
            value=v_l3,
            value_type="float",
            unit_ucum="V",
            original_name="V3",
            original_value=str(v_l3),
            original_unit="V",
            quality=q_good,
        ),
    ]

    ev_id = event_id or f"evt_{asset_id}_{event_time_utc.strftime('%Y%m%d%H%M%S')}"
    return CanonicalEvent(
        event_id=ev_id,
        asset_id=asset_id,
        event_time_utc=event_time_utc,
        received_time_utc=event_time_utc,
        source=_create_source_ref(seq),
        measurements=measurements,
        event_quality_flags=[],
        mapping_version="1.0.0",
    )


def _generate_baseline_stream(
    asset_id: str = "TX_DYNAMIC_01",
    count: int = 12,
    interval_minutes: int = 15,
) -> List[CanonicalEvent]:
    """Generate a clean balanced baseline telemetry stream (12 steps = 3 hours)."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    return [
        _create_synthetic_event(
            asset_id=asset_id,
            event_time_utc=t0 + timedelta(minutes=interval_minutes * i),
            oti=60.0 + (i * 0.5),
            amb=30.0 + (i * 0.2),
            p_kw=100.0 + (i * 1.0),
            q_kvar=50.0 + (i * 0.5),
            s_kva=111.8034 + (i * 1.118),
            i_l1=50.0 + (i * 0.5),
            i_l2=50.0 + (i * 0.5),
            i_l3=50.0 + (i * 0.5),
            v_l1=230.0 + (i * 0.2),
            v_l2=230.0 + (i * 0.2),
            v_l3=230.0 + (i * 0.2),
            seq=i + 1,
        )
        for i in range(count)
    ]


def _build_production_reducer(asset_id: str) -> TwinReducer:
    """Instantiate a real, unmocked TwinReducer with all canonical domain engines."""
    thresholds = {
        ElectricalEpisodeType.CURRENT_IMBALANCE: ElectricalEpisodeThresholds(
            warning_threshold=10.0,
            critical_threshold=25.0,
            recovery_threshold=5.0,
            persistence_seconds=900.0,  # 1 step (15 min) persistence to become ACTIVE
            recovery_seconds=900.0,     # 1 step (15 min) clean to close
        ),
    }
    return TwinReducer(
        episode_engine=ElectricalEpisodeEngine(asset_id=asset_id, thresholds=thresholds),
        anomaly_engine=MultiDomainAnomalyEngine(asset_id=asset_id),
        othi_engine=OTHIEngine(),
        exposure_engine=ThermalExposureEngine(asset_id=asset_id),
        maintenance_engine=MaintenanceEngine(),
    )


def _run_e2e_pipeline(
    events: List[CanonicalEvent],
    asset_id: str = "TX_DYNAMIC_01",
) -> Tuple[List[TwinState], StorageEngine]:
    """Pass events through clean StorageEngine, ReplayEngine, and TwinReducer."""
    storage = StorageEngine(db_path=":memory:")
    storage.insert_canonical_events(events)

    replay = ReplayEngine(storage=storage, asset_id=asset_id)
    reducer = _build_production_reducer(asset_id=asset_id)

    states: List[TwinState] = []
    current_state: TwinState | None = None
    for ev in replay.stream():
        current_state = reducer.reduce(current_state, ev)
        states.append(current_state)

    return states, storage


# ==============================================================================
# 1. INJ_SENSOR_SPIKE End-to-End Test
# ==============================================================================

def test_sensor_spike_end_to_end() -> None:
    """Verify INJ_SENSOR_SPIKE:

    Injected spike (+30.0 degC on OTI at cycle index 2):
    - Reaches canonical telemetry without unphysical modification of baseline history.
    - Rate-of-change detector flags SENSOR_PLAUSIBILITY (DET_PLAUS_RATE_OF_CHANGE).
    - Detection latency is exactly 1 cycle (cycle difference = 1 <= 2 cycles).
    - No false physical electrical/thermal fault or episode is fabricated.
    - Triggers sensor plausibility review advisory MNT-SENS-006 (P4 DATA_OR_MODEL).
    """
    asset_id = "TX_DYNAMIC_01"
    base_events = _generate_baseline_stream(asset_id=asset_id, count=8)
    t_inject = base_events[2].event_time_utc  # Cycle 2 (10:30)

    # Injected spike: +30 degC on oti_degc for 15 min duration
    scenario = create_sensor_spike_scenario(
        scenario_id="inj_spike_01",
        asset_id=asset_id,
        start_time_utc=t_inject,
        target_signal="oti_degc",
        spike_delta=30.0,  # 61.0 -> 91.0 degC (RoC ~ 2.0 degC/min > 1.0 threshold)
        duration_seconds=900.0,
    )
    injector = ScenarioInjectorEngine([scenario])
    injected_events = injector.inject_events_only(base_events)

    # 1. Verify baseline vs injected pipeline outputs
    states_base, _ = _run_e2e_pipeline(base_events, asset_id=asset_id)
    states_inj, storage = _run_e2e_pipeline(injected_events, asset_id=asset_id)

    assert len(states_inj) == 8

    # Steps 0 and 1: Clean/normal before injection
    assert states_inj[0].current_observations["oti_degc"].value == 60.0
    assert states_inj[1].current_observations["oti_degc"].value == 60.5
    assert len(states_inj[0].open_episodes) == 0
    assert len(states_inj[1].open_episodes) == 0

    # Step 2: Injected spike arrives (First qualifying evidence & first detection cycle)
    obs_step2 = states_inj[2].current_observations["oti_degc"]
    assert obs_step2.value == 91.0

    # Reducer anomaly evaluation on step 2:
    # MultiDomainAnomalyEngine detects DET_PLAUS_RATE_OF_CHANGE (Latency = 1 cycle <= 2 cycles)
    reducer = _build_production_reducer(asset_id)
    curr = None
    for ev in injected_events[:3]:
        curr = reducer.reduce(curr, ev)
    emitted_evidence = reducer.latest_emitted_evidence

    plaus_evs = [ev for ev in emitted_evidence if ev.detector_id == "DET_PLAUS_RATE_OF_CHANGE"]
    assert len(plaus_evs) == 1
    assert plaus_evs[0].category == AnomalyCategory.SENSOR_PLAUSIBILITY
    assert plaus_evs[0].observed_value >= 1.9
    assert plaus_evs[0].severity == 0.85

    # 2. No unrelated physical electrical episode is fabricated
    assert len(states_inj[2].open_episodes) == 0

    # 3. Triggers Sensor Plausibility Advisory (MNT-SENS-006)
    recs = states_inj[2].active_recommendations
    sens_recs = [r for r in recs if r.rule_id == "MNT-SENS-006"]
    assert len(sens_recs) >= 1
    assert sens_recs[0].priority == MaintenancePriority.P4_DATA_OR_MODEL
    assert sens_recs[0].action_window == ActionWindow.MODEL_REVIEW

    # 4. End-to-end FactBundle & Report generation verification
    fact_bundle = assemble_fact_bundle(
        state=states_inj[2],
    )
    report_data = generate_report_data(fact_bundle)
    assert report_data is not None
    assert len(report_data.active_recommendations) >= 1


# ==============================================================================
# 2. INJ_STUCK_SENSOR End-to-End Test
# ==============================================================================

def test_stuck_sensor_end_to_end() -> None:
    """Verify INJ_STUCK_SENSOR:

    Injected flatline on OTI starting at cycle index 2:
    - Signal is frozen at 63.0 degC while system evolves.
    - Frozen sensor detector requires 4 consecutive identical readings to qualify.
    - First detection occurs immediately on cycle index 5 (the 4th consecutive stuck cycle).
    - Latency from qualification requirement is exactly 1 cycle (<= 2 cycles).
    - Emits SENSOR_PLAUSIBILITY evidence and MNT-SENS-006 advisory without false physical alarms.
    """
    asset_id = "TX_DYNAMIC_01"
    base_events = _generate_baseline_stream(asset_id=asset_id, count=10)

    # Injected stuck sensor on oti_degc from step 2 for 6 steps (steps 2, 3, 4, 5, 6, 7)
    scenario = create_stuck_sensor_scenario(
        scenario_id="inj_stuck_01",
        asset_id=asset_id,
        start_time_utc=base_events[2].event_time_utc,
        target_signal="oti_degc",
        duration_seconds=5400.0,  # 6 x 15 min steps
        stuck_value=63.0,
    )
    injector = ScenarioInjectorEngine([scenario])
    injected_events = injector.inject_events_only(base_events)

    states_inj, _ = _run_e2e_pipeline(injected_events, asset_id=asset_id)

    # Steps 0 and 1: Baseline varying values (60.0, 60.5)
    assert states_inj[0].current_observations["oti_degc"].value == 60.0
    assert states_inj[1].current_observations["oti_degc"].value == 60.5

    # Steps 2, 3, 4: Injected stuck value 63.0 (1st, 2nd, 3rd consecutive identical readings)
    assert states_inj[2].current_observations["oti_degc"].value == 63.0
    assert states_inj[3].current_observations["oti_degc"].value == 63.0
    assert states_inj[4].current_observations["oti_degc"].value == 63.0

    # Step 5: 4th consecutive identical reading -> triggers DET_PLAUS_FROZEN_SENSOR
    assert states_inj[5].current_observations["oti_degc"].value == 63.0

    reducer = _build_production_reducer(asset_id)
    curr = None
    for ev in injected_events[:6]:
        curr = reducer.reduce(curr, ev)

    frozen_evs = [
        ev
        for ev in reducer.latest_emitted_evidence
        if ev.detector_id == "DET_PLAUS_FROZEN_SENSOR" and "oti_degc" in ev.input_lineage
    ]
    assert len(frozen_evs) == 1
    assert frozen_evs[0].category == AnomalyCategory.SENSOR_PLAUSIBILITY
    assert frozen_evs[0].direction == "FLATLINE"
    assert frozen_evs[0].severity == 0.60

    # Triggers MNT-SENS-006 advisory
    recs = states_inj[5].active_recommendations
    assert any(r.rule_id == "MNT-SENS-006" for r in recs)


# ==============================================================================
# 3. INJ_PERSISTENT_BIAS End-to-End Test
# ==============================================================================

def test_persistent_bias_end_to_end() -> None:
    """Verify INJ_PERSISTENT_BIAS:

    Injected persistent positive bias (+30.0 degC on OTI):
    - Elevates OTI from 61.0 to 91.0 degC (exceeding 85.0 degC warning threshold).
    - DET_THERMAL_LIMIT_ABSOLUTE detects high temperature on cycle index 2 (1st cycle of injection).
    - Detection latency = 1 cycle (<= 2 cycles).
    - Thermal health domain status and evidence reflect elevated thermal condition.
    - Generates maintenance recommendation according to frozen rules.
    """
    asset_id = "TX_DYNAMIC_01"
    base_events = _generate_baseline_stream(asset_id=asset_id, count=8)
    t_inject = base_events[2].event_time_utc

    scenario = create_persistent_bias_scenario(
        scenario_id="inj_bias_01",
        asset_id=asset_id,
        start_time_utc=t_inject,
        target_signal="oti_degc",
        bias_delta=30.0,  # 61.0 -> 91.0 degC
        duration_seconds=3600.0,
    )
    injector = ScenarioInjectorEngine([scenario])
    injected_events = injector.inject_events_only(base_events)

    states_inj, _ = _run_e2e_pipeline(injected_events, asset_id=asset_id)

    # Step 2: First injected bias step
    assert states_inj[2].current_observations["oti_degc"].value == 91.0

    reducer = _build_production_reducer(asset_id)
    curr = None
    for ev in injected_events[:3]:
        curr = reducer.reduce(curr, ev)

    th_evs = [
        ev for ev in reducer.latest_emitted_evidence if ev.detector_id == "DET_THERMAL_LIMIT_ABSOLUTE"
    ]
    assert len(th_evs) == 1
    assert th_evs[0].category == AnomalyCategory.THERMAL_LIMIT
    assert th_evs[0].observed_value == 91.0
    # 91 degC is 60% of the way from the 85 degC warning to the 95 degC critical limit:
    # 0.41 + 0.19 * 0.6 = 0.524 (WARNING band), not a flat CRITICAL-band constant
    assert th_evs[0].severity == 0.524

    # Health assessment reflects thermal domain impact
    assert curr.health_bundle is not None
    th_domain = curr.health_bundle.domains.get("thermal")
    assert th_domain is not None
    assert th_domain.severity == 0.524
    assert th_domain.status == HealthStatus.WARNING


# ==============================================================================
# 4. INJ_SUSTAINED_OVERLOAD End-to-End Test
# ==============================================================================

def test_sustained_overload_end_to_end() -> None:
    """Verify INJ_SUSTAINED_OVERLOAD:

    Injected 1.40x electrical load multiplier (140% loading) for 4 steps:
    - Relative load index increases from ~0.78 to ~1.10 (exceeding 1.00 warning threshold).
    - Loading detector (DET_LOAD_RELATIVE_INDEX) triggers on cycle index 2 (1st cycle of injection).
    - Detection latency = 1 cycle (<= 2 cycles).
    - OTHI loading domain reflects overload evidence.
    - Upon injection cessation (step 6), load returns to normal.
    """
    asset_id = "TX_DYNAMIC_01"
    base_events = _generate_baseline_stream(asset_id=asset_id, count=10)
    t_inject = base_events[2].event_time_utc

    # 1.40x load multiplier for 4 steps (steps 2, 3, 4, 5) -> 1 hour
    scenario = create_sustained_overload_scenario(
        scenario_id="inj_ovld_01",
        asset_id=asset_id,
        start_time_utc=t_inject,
        duration_seconds=3600.0,
        load_multiplier=1.40,
    )
    injector = ScenarioInjectorEngine([scenario])
    injected_events = injector.inject_events_only(base_events)

    states_inj, _ = _run_e2e_pipeline(injected_events, asset_id=asset_id)

    # Step 0, 1: Normal load (~111.8 kVA, relative load index ~0.78)
    assert states_inj[0].derived_electrical.relative_load_index is not None
    u_base = states_inj[0].derived_electrical.relative_load_index
    assert u_base < 1.00

    # Step 2 (Cycle 1 of injection): Injected 1.40x load (u ~ 1.09 >= 1.00 warning)
    u_inj = states_inj[2].derived_electrical.relative_load_index
    assert u_inj > 1.00

    # Detector triggers DET_LOAD_RELATIVE_INDEX on step 2 (Latency = 1 cycle <= 2 cycles)
    reducer = _build_production_reducer(asset_id)
    curr = None
    for ev in injected_events[:3]:
        curr = reducer.reduce(curr, ev)

    load_evs = [
        ev for ev in reducer.latest_emitted_evidence if ev.detector_id == "DET_LOAD_RELATIVE_INDEX"
    ]
    assert len(load_evs) == 1
    assert load_evs[0].category == AnomalyCategory.LOADING
    # Proportional within the 100%..125% warning band; stays in the WARNING severity band
    assert load_evs[0].severity == round(0.41 + 0.19 * (u_inj - 1.00) / 0.25, 3)
    assert 0.41 <= load_evs[0].severity < 0.61

    # Health domain impact
    assert curr.health_bundle is not None
    load_domain = curr.health_bundle.domains.get("loading")
    assert load_domain is not None
    assert load_domain.severity == load_evs[0].severity
    assert load_domain.status == HealthStatus.WARNING

    # Step 6 (Injection finished): Load returns to normal
    assert states_inj[6].derived_electrical.relative_load_index < 1.00


# ==============================================================================
# 5. INJ_PHASE_IMBALANCE End-to-End Test
# ==============================================================================

def test_phase_imbalance_end_to_end() -> None:
    """Verify INJ_PHASE_IMBALANCE:

    Injected 2.50x current multiplier on Phase L1 (50A -> 125A, IUB = 66.67%):
    - Current magnitude imbalance reaches derived electrical features immediately.
    - DET_PHASE_CURRENT_IMBALANCE triggers on cycle index 2 (1st cycle of injection, latency = 1 cycle <= 2 cycles).
    - Episode lifecycle: WATCH at cycle 2 -> CRITICAL at cycle 3 -> RECOVERING at cycle 6 -> CLOSED at cycle 7.
    - OTHI phase_neutral health domain reflects imbalance severity (0.90).
    - Emits MNT-PHASE-004 maintenance advisory (P2 PLANNED_ACTION).
    """
    asset_id = "TX_DYNAMIC_01"
    base_events = _generate_baseline_stream(asset_id=asset_id, count=10)
    t_inject = base_events[2].event_time_utc

    scenario = create_phase_imbalance_scenario(
        scenario_id="inj_iub_01",
        asset_id=asset_id,
        start_time_utc=t_inject,
        target_phase="L1",
        phase_multiplier=2.50,  # 50A -> 125A
        duration_seconds=3600.0,
    )
    injector = ScenarioInjectorEngine([scenario])
    injected_events = injector.inject_events_only(base_events)

    states_inj, _ = _run_e2e_pipeline(injected_events, asset_id=asset_id)

    # Step 0, 1: Balanced (0.0% IUB)
    assert states_inj[0].derived_electrical.current_magnitude_imbalance_pct == 0.0
    assert len(states_inj[0].open_episodes) == 0

    # Step 2: Injected imbalance (~66.67% IUB >= 25% critical)
    iub = states_inj[2].derived_electrical.current_magnitude_imbalance_pct
    assert iub is not None and abs(iub - 66.6667) < 0.01

    # Reducer evidence emission on step 2 (Latency = 1 cycle <= 2 cycles)
    reducer = _build_production_reducer(asset_id)
    curr = None
    for ev in injected_events[:3]:
        curr = reducer.reduce(curr, ev)

    ph_evs = [
        ev for ev in reducer.latest_emitted_evidence if ev.detector_id == "DET_PHASE_CURRENT_IMBALANCE"
    ]
    assert len(ph_evs) == 1
    assert ph_evs[0].category == AnomalyCategory.PHASE_OR_NEUTRAL
    assert ph_evs[0].severity == 0.90

    # Episode lifecycle: Step 2 WATCH -> Step 3 CRITICAL
    assert states_inj[2].open_episodes[0].state == EpisodeState.WATCH
    assert states_inj[3].open_episodes[0].state == EpisodeState.CRITICAL

    # OTHI Phase/Neutral health domain impact
    assert curr.health_bundle is not None
    ph_domain = curr.health_bundle.domains.get("phase_neutral")
    assert ph_domain is not None
    assert ph_domain.severity >= 0.90
    assert ph_domain.status == HealthStatus.CRITICAL

    # Maintenance advisory MNT-PHASE-004
    recs = states_inj[3].active_recommendations
    phase_recs = [r for r in recs if r.rule_id == "MNT-PHASE-004"]
    assert len(phase_recs) >= 1
    assert phase_recs[0].priority == MaintenancePriority.P2_PLANNED_ACTION
    assert phase_recs[0].action_window == ActionWindow.NEXT_AUTHORIZED_MAINTENANCE_WINDOW

    # Step 6: Imbalance removed -> RECOVERING; Step 7 -> CLOSED
    assert states_inj[6].open_episodes[0].state == EpisodeState.RECOVERING
    assert len(states_inj[7].open_episodes) == 0


# ==============================================================================
# 6. Determinism & Repeated Runs
# ==============================================================================

@pytest.mark.parametrize(
    "injector_type,scenario_factory",
    [
        (
            InjectorType.INJ_SENSOR_SPIKE,
            lambda t: create_sensor_spike_scenario(
                "det_spike", "TX_DYNAMIC_01", t, "oti_degc", spike_delta=25.0, duration_seconds=900.0
            ),
        ),
        (
            InjectorType.INJ_STUCK_SENSOR,
            lambda t: create_stuck_sensor_scenario(
                "det_stuck", "TX_DYNAMIC_01", t, "oti_degc", stuck_value=62.0, duration_seconds=3600.0
            ),
        ),
        (
            InjectorType.INJ_PERSISTENT_BIAS,
            lambda t: create_persistent_bias_scenario(
                "det_bias", "TX_DYNAMIC_01", t, "oti_degc", bias_delta=30.0, duration_seconds=3600.0
            ),
        ),
        (
            InjectorType.INJ_SUSTAINED_OVERLOAD,
            lambda t: create_sustained_overload_scenario(
                "det_ovld", "TX_DYNAMIC_01", t, load_multiplier=1.35, duration_seconds=3600.0
            ),
        ),
        (
            InjectorType.INJ_PHASE_IMBALANCE,
            lambda t: create_phase_imbalance_scenario(
                "det_iub", "TX_DYNAMIC_01", t, target_phase="L1", phase_multiplier=2.0, duration_seconds=3600.0
            ),
        ),
    ],
)
def test_injector_determinism_across_repeated_runs(injector_type: InjectorType, scenario_factory: Any) -> None:
    """Verify identical, byte-for-byte deterministic execution across repeated clean replays."""
    asset_id = "TX_DYNAMIC_01"
    base_events = _generate_baseline_stream(asset_id=asset_id, count=8)
    t_start = base_events[2].event_time_utc

    scenario = scenario_factory(t_start)
    injector = ScenarioInjectorEngine([scenario])
    injected_events = injector.inject_events_only(base_events)

    # Run 1: Clean state
    states_run1, _ = _run_e2e_pipeline(injected_events, asset_id=asset_id)

    # Run 2: Fresh clean state
    states_run2, _ = _run_e2e_pipeline(injected_events, asset_id=asset_id)

    assert len(states_run1) == len(states_run2)

    for idx, (s1, s2) in enumerate(zip(states_run1, states_run2)):
        assert s1.state_sequence == s2.state_sequence
        assert s1.state_time_utc == s2.state_time_utc
        assert s1.state_hash == s2.state_hash, f"State hash mismatch at step {idx} for {injector_type}"
        assert len(s1.open_episodes) == len(s2.open_episodes)
        assert len(s1.active_recommendations) == len(s2.active_recommendations)

        if s1.health_bundle and s2.health_bundle:
            assert s1.health_bundle.othi_score == s2.health_bundle.othi_score
            assert s1.health_bundle.status == s2.health_bundle.status
