"""Regression tests for proportional OTHI scoring.

Root cause covered: analog detectors emitted one constant severity per band, so every warning-level
excursion produced the same OTHI (e.g. 40 or 30) regardless of magnitude, and several "warning"
constants (0.65 / 0.70) sat in the CRITICAL severity band. Warning-band severity is now linear
between each detector's documented warning and critical thresholds, mapped onto [0.41, 0.60].
A DEMO_DEFAULT watch tier (linear onto [0.21, 0.40]) covers readings approaching a warning limit,
as the architecture's normal/watch/warning/critical piecewise-linear severity rule requires.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.engine.anomaly_detectors import (
    detect_loading,
    detect_thermal_limits,
    is_watch_level_evidence,
    warning_band_severity,
    watch_band_severity,
)
from app.engine.maintenance import MaintenanceEngine
from app.engine.othi import OTHIEngine, aggregate_othi_v2, status_from_severity
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.features import DerivedFeatures
from app.models.health import HealthStatus
from app.models.telemetry import CanonicalEvent, Measurement, MeasurementQuality, QualitySeverity, SourceRef

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
STEP = timedelta(minutes=15)


def _meas(signal_id, value, unit="A", phase=None, severity=QualitySeverity.GOOD):
    return Measurement(
        signal_id=signal_id,
        phase=phase,
        value=value,
        value_type="bool" if isinstance(value, bool) else ("int" if isinstance(value, int) else "float"),
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=[]),
    )


def _event(i, top_oil=60.0, extra=None):
    # Ambient 40 degC keeps the rise-over-ambient detector below its 55 degC warning up to 94 degC
    meas = [
        _meas("top_oil_temperature", top_oil, "Cel"),
        _meas("ambient_temperature", 40.0, "Cel"),
        _meas("current_l1", 100.0, phase="L1"),
        _meas("current_l2", 100.0, phase="L2"),
        _meas("current_l3", 100.0, phase="L3"),
        _meas("voltage_l1_n", 230.0, "V", phase="L1"),
        _meas("voltage_l2_n", 230.0, "V", phase="L2"),
        _meas("voltage_l3_n", 230.0, "V", phase="L3"),
        _meas("power_factor_total", 0.95, "1"),
    ] + list(extra or [])
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=f"ev-{i}",
        asset_id="DT-PROP",
        event_time_utc=T0 + i * STEP,
        received_time_utc=None,
        source=SourceRef(
            system="test_gridpulse",
            adapter_id="adapter_test",
            source_record_id=f"row_{i}",
            source_uri="fixtures/test.csv",
            raw_sha256="abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        ),
        measurements=meas,
        event_quality_flags=[],
        mapping_version="1.0.0",
    )


def _engine():
    return OTHIEngine(expected_cadence_seconds=900.0, algorithm_version="OTHI_V2")


def _score(engine, i, top_oil, evidence_extra=()):
    ev = _event(i, top_oil)
    evidence = detect_thermal_limits(ev) + list(evidence_extra)
    return engine.evaluate(event=ev, evidence_items=evidence)


def _loading_evidence(i, u):
    return detect_loading(_event(i), derived=DerivedFeatures(timestamp_utc=T0 + i * STEP, relative_load_index=u))


def test_warning_band_severity_is_proportional_and_stays_in_warning_band():
    assert warning_band_severity(85.0, 85.0, 95.0) == 0.41
    assert warning_band_severity(90.0, 85.0, 95.0) == 0.505
    assert warning_band_severity(94.9, 85.0, 95.0) == pytest.approx(0.598, abs=1e-3)
    # Falling limits (power factor, oil level) map the same way
    assert warning_band_severity(0.85, 0.85, 0.70) == 0.41
    assert warning_band_severity(0.775, 0.85, 0.70) == 0.505
    for v in (85.0, 88.0, 92.0, 94.99):
        assert status_from_severity(warning_band_severity(v, 85.0, 95.0)) == HealthStatus.WARNING


def test_healthy_frame_scores_100():
    bundle = _score(_engine(), 0, 60.0)
    assert bundle.othi_score == 100
    assert bundle.total_penalty == 0.0
    assert all(d.severity == 0.0 for d in bundle.domains.values())


def test_single_moderate_penalty_follows_documented_formula():
    bundle = _score(_engine(), 0, 91.0)
    # 91 degC: 0.41 + 0.19 * (91 - 85) / 10 = 0.524 -> OTHI round(100 * 0.476) = 48
    assert bundle.domains["thermal"].severity == 0.524
    assert bundle.driving_domain == "thermal"
    assert bundle.othi_score == 48
    assert bundle.status == HealthStatus.WARNING


def test_increasing_severity_is_proportional_and_never_improves_score():
    temps = [74.0, 75.0, 78.0, 81.0, 84.9, 85.0, 87.0, 89.0, 91.0, 93.0, 94.5, 95.0, 97.0]
    scores = [_score(_engine(), 0, t).othi_score for t in temps]
    assert scores == sorted(scores, reverse=True)
    # Watch and warning bands track magnitude instead of one constant value
    assert len(set(scores[1:11])) == 10
    assert scores[0] == 100  # below the watch threshold: no detection
    assert scores[1] == 79 and scores[4] == 60  # watch band spans 79..60
    assert scores[5] == 59 and scores[-1] == 5  # warning onset vs. critical top-oil (0.95)


def test_independent_secondary_domain_never_improves_and_compounds_per_formula():
    alone = _score(_engine(), 0, 91.0)
    load_ev = _loading_evidence(0, 1.10)
    s_load = load_ev[0].severity
    assert s_load == warning_band_severity(1.10, 1.00, 1.25)
    both = _score(_engine(), 0, 91.0, load_ev)
    assert both.othi_score <= alone.othi_score
    expected_total = 0.524 + 0.25 * (1 - 0.524) * s_load
    assert both.total_penalty == pytest.approx(expected_total)
    assert both.othi_score == round(100 * (1 - expected_total))


def test_tied_base_severities_pick_alphabetical_domain_and_count_once():
    score, base, sec, total, driver = aggregate_othi_v2({"thermal": 0.5, "loading": 0.5})
    assert driver == "loading"
    assert base == 0.5
    assert sec == pytest.approx(0.25 * 0.5 * 0.5)
    assert total == pytest.approx(0.5625)
    assert score == 44
    assert aggregate_othi_v2({"loading": 0.5, "thermal": 0.5}) == (score, base, sec, total, driver)


def test_same_domain_detectors_are_not_double_counted():
    ev = _event(0, 91.0)
    dup = detect_thermal_limits(ev)[0].model_copy(update={"evidence_id": "dup", "detector_id": "DET_THERMAL_LIMIT_OTI"})
    bundle = _engine().evaluate(event=ev, evidence_items=detect_thermal_limits(ev) + [dup])
    assert bundle.othi_score == 48


def _item(detector_id, category, severity):
    return EvidenceItem(
        evidence_id=f"ev-{detector_id}",
        asset_id="DT-PROP",
        event_time_utc=T0,
        category=category,
        detector_id=detector_id,
        observed_value=1.0,
        expected_value=0.0,
        unit="1",
        threshold_or_band="test",
        direction="HIGH",
        severity=severity,
        confidence=0.9,
        input_lineage=["top_oil_temperature"],
        reason_codes=["TEST"],
        hypothesis_codes=["TEST"],
    )


def test_shadow_only_and_data_quality_evidence_do_not_penalize():
    shadow = _item("DET_THERMAL_CUSUM_DRIFT", AnomalyCategory.THERMAL_DEVIATION, 0.75)
    dq = _item("DET_DQ_MEASUREMENT_QUALITY", AnomalyCategory.DATA_QUALITY, 0.70)
    bundle = _score(_engine(), 0, 60.0, [shadow, dq])
    assert bundle.othi_score == 100
    assert bundle.evidence_grade.value == "C"  # quality issue lowers grade, not physical health


def test_bad_quality_trip_contact_does_not_latch():
    ev = _event(0, extra=[_meas("buchholz_trip", 1, "1", severity=QualitySeverity.BAD)])
    engine = _engine()
    bundle = engine.evaluate(event=ev, evidence_items=[])
    assert bundle.othi_score == 100
    assert engine.latched_protection_trip is False


def test_genuine_trip_scores_zero_and_stays_latched_without_resolution():
    engine = _engine()
    trip = engine.evaluate(event=_event(0, extra=[_meas("buchholz_trip", 1, "1")]), evidence_items=[])
    assert trip.othi_score == 0 and trip.status == HealthStatus.CRITICAL
    after = engine.evaluate(event=_event(1), evidence_items=[])
    assert after.othi_score == 0
    assert engine.latched_protection_trip is True


def test_recovery_clears_penalty_immediately_without_stale_score():
    engine = _engine()
    assert _score(engine, 0, 93.0).othi_score == 44
    assert _score(engine, 1, 89.0).othi_score == 51
    assert _score(engine, 2, 60.0).othi_score == 100


def test_replay_of_same_ordered_input_is_deterministic():
    temps = [60.0, 86.0, 91.0, 96.0, 88.0, 60.0]
    runs = []
    for _ in range(2):
        engine = _engine()
        runs.append([_score(engine, i, t).othi_score for i, t in enumerate(temps)])
    assert runs[0] == runs[1]
    assert runs[0] == [100, 57, 48, 5, 53, 100]


def test_watch_band_scores_between_60_and_79():
    assert watch_band_severity(75.0, 75.0, 85.0) == 0.21
    assert watch_band_severity(0.95, 0.90, 1.00) == pytest.approx(0.305)
    assert watch_band_severity(0.875, 0.90, 0.85) == pytest.approx(0.305)  # falling limit (PF)
    bundle = _score(_engine(), 0, 79.0)
    # 79 degC: 0.21 + 0.19 * (79 - 75) / 10 = 0.286 -> OTHI round(71.4) = 71
    assert bundle.domains["thermal"].severity == 0.286
    assert bundle.othi_score == 71
    assert bundle.status == HealthStatus.WATCH


def test_watch_level_evidence_raises_no_maintenance_advisory():
    ev = _event(0, 79.0)
    watch = detect_thermal_limits(ev)
    assert len(watch) == 1 and is_watch_level_evidence(watch[0])
    assert not [r for r in MaintenanceEngine().evaluate(event=ev, evidence_items=watch) if r.rule_id == "MNT-THERM-002"]
    warn = detect_thermal_limits(_event(1, 91.0))
    assert not is_watch_level_evidence(warn[0])
    assert [r for r in MaintenanceEngine().evaluate(event=_event(1, 91.0), evidence_items=warn) if r.rule_id == "MNT-THERM-002"]


def test_uncalibrated_watch_tiers_stay_disabled():
    # Normal operation on both datasets sits in these would-be watch ranges, so no watch evidence
    from app.engine.anomaly_detectors import detect_phase_neutral, detect_voltage_pf_frequency

    derived = DerivedFeatures(
        timestamp_utc=T0,
        current_magnitude_imbalance_pct=7.0,
        neutral_current_ratio=0.15,
        voltage_magnitude_imbalance_pct=1.5,
        power_factor_derived=0.87,
    )
    ev = _event(0)
    assert detect_phase_neutral(ev, derived=derived) == []
    assert detect_voltage_pf_frequency(ev, derived=derived) == []


def _thermal_evidence(engine, i, top_oil, ambient=40.0):
    ev = _event(i, top_oil)
    ev = ev.model_copy(update={"measurements": [
        m if m.signal_id != "ambient_temperature" else _meas("ambient_temperature", ambient, "Cel")
        for m in ev.measurements
    ]})
    return [e for e in engine.evaluate_event(ev) if e.category == AnomalyCategory.THERMAL_LIMIT]


def test_frozen_top_oil_produces_no_thermal_penalty_once_flagged():
    # DT-01 SC-...-TOPOIL_FROZEN ground truth: "frozen-sensor check should flag it, no thermal alarm"
    from app.engine.anomaly_detectors import MultiDomainAnomalyEngine

    engine = MultiDomainAnomalyEngine(asset_id="DT-PROP")
    results = [_thermal_evidence(engine, i, 72.2, ambient=a) for i, a in enumerate([30.0, 28.0, 26.0, 24.0, 22.0])]
    assert results[0] == []  # rise 42.2: below watch
    assert results[1] == [] or results[1][0].detector_id == "DET_THERMAL_LIMIT_RISE"
    assert results[3] == [] and results[4] == []  # 4+ identical readings: frozen, suppressed


def test_constant_reference_and_contact_signals_are_not_flagged_frozen():
    from app.engine.anomaly_detectors import detect_sensor_plausibility

    history = {}
    flagged = []
    for i in range(6):
        ev = _event(i, extra=[
            _meas("oil_level_ref_pct", 30.0, "%"),
            _meas("oil_level_ref_temp_c", 30.0, "Cel"),
            _meas("lv_breaker_closed", 1.0, "1"),
        ])
        flagged += [s for e in detect_sensor_plausibility(ev, history) for s in e.input_lineage]
        for m in ev.measurements:
            history.setdefault(m.signal_id if m.phase is None else f"{m.signal_id}_{m.phase}", []).append((ev.event_time_utc, m.value))
    assert not {"oil_level_ref_pct", "oil_level_ref_temp_c", "lv_breaker_closed"} & set(flagged)


def test_shadow_only_cusum_does_not_raise_p1_thermal_inspection():
    cusum = _item("DET_THERMAL_CUSUM_DRIFT", AnomalyCategory.THERMAL_DEVIATION, 0.75)
    engine = MaintenanceEngine(is_thermal_qualified=True, cusum_qualification="ENABLED")
    recs = engine.evaluate(event=_event(0), evidence_items=[cusum])
    assert not [r for r in recs if r.rule_id == "MNT-THERM-002"]
