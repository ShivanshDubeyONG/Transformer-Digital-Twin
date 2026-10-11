"""Phase 5.4 — Multi-Domain Anomaly Detectors & Evidence Integration Engine.

Implements modular, deterministic anomaly detectors across the 8 canonical categories:
1. DATA_QUALITY
2. SENSOR_PLAUSIBILITY
3. THERMAL_DEVIATION
4. THERMAL_LIMIT
5. LOADING
6. PHASE_OR_NEUTRAL
7. VOLTAGE_PF_FREQUENCY
8. PROTECTION_OR_OIL_STATUS

Emits standardized EvidenceItem records with deterministic severity, confidence,
and input lineage while strictly honoring capability qualification gates.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple
from pydantic import BaseModel, ConfigDict, Field

from app.engine.thermal_fallback import ThermalRuntimeOutput
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.features import DerivedFeatures
from app.models.profile import AssetProfile
from app.models.telemetry import CanonicalEvent, Measurement, QualitySeverity
from app.models.thermal_artifact import QualificationStatus, ThermalModelQualification


# ---------------------------------------------------------------------------
# Configuration Models
# ---------------------------------------------------------------------------

class AnomalyDetectorThresholds(BaseModel):
    """Configurable engineering and operational anomaly detection thresholds."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    # Thermal Limit Thresholds
    oti_warning_degc: float = Field(default=85.0, description="Top-oil temperature warning threshold in degC")
    oti_critical_degc: float = Field(default=95.0, description="Top-oil temperature critical threshold in degC")
    rise_warning_degc: float = Field(default=55.0, description="Top-oil rise over ambient warning threshold in degC")
    rise_critical_degc: float = Field(default=65.0, description="Top-oil rise over ambient critical threshold in degC")

    # Loading Thresholds
    load_u_warning: float = Field(default=1.00, description="Relative load index warning threshold (100% capacity)")
    load_u_critical: float = Field(default=1.25, description="Relative load index critical threshold (125% capacity)")

    # Phase and Neutral Thresholds
    current_imbalance_warning_pct: float = Field(default=10.0, description="NEMA current imbalance warning threshold %")
    current_imbalance_critical_pct: float = Field(default=25.0, description="NEMA current imbalance critical threshold %")
    neutral_ratio_warning: float = Field(default=0.20, description="Neutral current ratio warning threshold")
    neutral_ratio_critical: float = Field(default=0.50, description="Neutral current ratio critical threshold")

    # Voltage / PF Thresholds
    voltage_imbalance_warning_pct: float = Field(default=2.0, description="NEMA voltage imbalance warning threshold %")
    voltage_imbalance_critical_pct: float = Field(default=3.0, description="NEMA voltage imbalance critical threshold %")
    pf_warning: float = Field(default=0.85, description="Power factor warning threshold (lower is worse)")
    pf_critical: float = Field(default=0.70, description="Power factor critical threshold (lower is worse)")
    v_nominal_v: float = Field(default=240.0, description="Nominal phase-to-neutral voltage in Volts")
    undervoltage_ratio: float = Field(default=0.90, description="Undervoltage threshold ratio (0.90 * V_nominal)")
    overvoltage_ratio: float = Field(default=1.10, description="Overvoltage threshold ratio (1.10 * V_nominal)")

    # Protection & Oil Status Thresholds
    oil_level_warning_pct: float = Field(default=25.0, description="Oil level percentage warning threshold %")
    oil_level_critical_pct: float = Field(default=10.0, description="Oil level percentage critical threshold %")
    oil_leak_trend_threshold_pct_per_day: float = Field(
        default=-0.10, description="Rate of decline threshold in %/day indicating suspected oil loss"
    )
    tank_pressure_warning_kpa_g: float = Field(
        default=25.0, description="Sealed tank gauge pressure warning threshold in kPa(g)"
    )
    tank_pressure_low_kpa_g: float = Field(
        default=-10.0, description="Sealed tank gauge pressure minimum threshold in kPa(g)"
    )

    # Data Quality & Plausibility Thresholds
    pqs_inconsistency_threshold: float = Field(default=0.10, description="P-Q-S inconsistency error threshold")
    oti_max_rate_degc_per_min: float = Field(
        default=1.0, description="Max plausible top-oil temperature rate of change (degC/min)"
    )
    oti_max_step_degc: float = Field(
        default=10.0, description="Max plausible single-step top-oil temperature change in degC"
    )
    stuck_consecutive_steps: int = Field(
        default=4, description="Consecutive identical readings required to flag flatline/stuck sensor"
    )
    temp_flatline_min_steps: int = Field(
        default=4, description="Consecutive identical readings required for temperature sensor flatline"
    )
    threshold_provenance: str = Field(
        default="CONFIGURED_ENGINEERING_DEFAULT",
        description="Explicit provenance label distinguishing configured engineering assumptions/defaults from verified nameplate/standards limits",
    )


DEFAULT_DETECTOR_THRESHOLDS = AnomalyDetectorThresholds()

# Severity band for a reading between a detector's warning and critical thresholds. It matches the
# WARNING band of othi.status_from_severity ([0.41, 0.61)), so a warning-level excursion reports a
# WARNING domain and lands in the WARNING OTHI band (59..40), never CRITICAL.
WARNING_BAND_SEVERITY_FLOOR = 0.41
WARNING_BAND_SEVERITY_CEILING = 0.60


def warning_band_severity(value: float, warning: float, critical: float) -> float:
    """Severity proportional to how far `value` sits between the warning and critical thresholds.

    Linear in the documented [warning, critical) interval, mapped onto the WARNING severity band:
    the floor at the warning threshold, approaching the ceiling as the reading nears critical.
    Works for both rising (warning < critical) and falling (warning > critical) limits. Readings at
    or past critical are the caller's critical branch and keep their discrete critical severity.
    """
    span = critical - warning
    fraction = 0.0 if span == 0 else (value - warning) / span
    fraction = max(0.0, min(1.0, fraction))
    severity = WARNING_BAND_SEVERITY_FLOOR + (
        WARNING_BAND_SEVERITY_CEILING - WARNING_BAND_SEVERITY_FLOOR
    ) * fraction
    return round(severity, 3)

# Declared asset metadata carried in the telemetry stream (constant by definition, not a sensor).
STATIC_METADATA_SIGNALS: frozenset[str] = frozenset({"rated_kva"})


# ---------------------------------------------------------------------------
# Individual Domain Detector Functions
# ---------------------------------------------------------------------------


def detect_data_quality(
    event: CanonicalEvent,
    derived: Optional[DerivedFeatures] = None,
    thresholds: AnomalyDetectorThresholds = DEFAULT_DETECTOR_THRESHOLDS,
) -> List[EvidenceItem]:
    """Detect data quality, bad quality severity, out-of-bounds, and P-Q-S inconsistency."""
    evidence: List[EvidenceItem] = []
    t_str = event.event_time_utc.strftime("%Y%m%d%H%M%S")

    # 1. Measurement-level BAD or UNCERTAIN quality severity
    for idx, m in enumerate(event.measurements):
        if m.quality.severity in (QualitySeverity.BAD, QualitySeverity.UNCERTAIN):
            flags_desc = ", ".join(m.quality.flags) if m.quality.flags else m.quality.severity.value
            ev_id = f"ev_{event.asset_id}_dq_quality_{m.signal_id}_{t_str}_{idx}"
            evidence.append(
                EvidenceItem(
                    evidence_id=ev_id,
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.DATA_QUALITY,
                    detector_id="DET_DQ_MEASUREMENT_QUALITY",
                    observed_value=str(m.value),
                    expected_value="GOOD",
                    unit=m.unit_ucum,
                    threshold_or_band="QualitySeverity.GOOD",
                    direction=None,
                    severity=0.70 if m.quality.severity == QualitySeverity.BAD else 0.40,
                    confidence=1.0,
                    input_lineage=[m.signal_id],
                    reason_codes=["MEASUREMENT_QUALITY_FLAGGED", f"FLAG_{flags_desc}"],
                    hypothesis_codes=["INSTRUMENTATION_CORRUPTION", "COMMUNICATION_FAULT"],
                )
            )

    # 2. Envelope-level Quality Flags
    if event.event_quality_flags:
        for idx, flag in enumerate(event.event_quality_flags):
            # Partition metadata and operational/validation states are not data-quality faults
            if flag.startswith("PARTITION_") or flag in (
                "PROTECTION_TRIP_ACTIVE",
                "DIRECT_PROTECTION_TRIP",
                "VALIDATED",
            ):
                continue
            ev_id = f"ev_{event.asset_id}_dq_envflag_{flag}_{t_str}_{idx}"
            evidence.append(
                EvidenceItem(
                    evidence_id=ev_id,
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.DATA_QUALITY,
                    detector_id="DET_DQ_ENVELOPE_FLAG",
                    observed_value=flag,
                    expected_value=None,
                    unit=None,
                    threshold_or_band=None,
                    direction=None,
                    severity=0.50,
                    confidence=1.0,
                    input_lineage=[event.event_id],
                    reason_codes=[f"ENVELOPE_FLAG_{flag}"],
                    hypothesis_codes=["INGESTION_ANOMALY"],
                )
            )

    # 3. P-Q-S Inconsistency Metric (Strictly DATA_QUALITY evidence per Phase 5.1 design)
    if derived is not None and derived.pqs_inconsistency is not None:
        if derived.pqs_inconsistency >= thresholds.pqs_inconsistency_threshold:
            ev_id = f"ev_{event.asset_id}_dq_pqs_{t_str}"
            evidence.append(
                EvidenceItem(
                    evidence_id=ev_id,
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.DATA_QUALITY,
                    detector_id="DET_DQ_PQS_INCONSISTENCY",
                    observed_value=round(derived.pqs_inconsistency, 4),
                    expected_value=0.0,
                    unit="ratio",
                    threshold_or_band=f"< {thresholds.pqs_inconsistency_threshold}",
                    direction="HIGH",
                    severity=min(1.0, 0.50 + derived.pqs_inconsistency),
                    confidence=0.95,
                    input_lineage=["active_power", "reactive_power", "apparent_power"],
                    reason_codes=["PQS_TRIANGLE_INCONSISTENCY"],
                    hypothesis_codes=["CT_PT_RATIO_MISMATCH", "TRANSDUCER_METER_DESYNC"],
                )
            )

    return evidence


def detect_sensor_plausibility(
    event: CanonicalEvent,
    history_buffer: Dict[str, List[Tuple[datetime, float]]],
    thresholds: AnomalyDetectorThresholds = DEFAULT_DETECTOR_THRESHOLDS,
) -> List[EvidenceItem]:
    """Detect sensor flatlining/stuck values and physically impossible rate-of-change steps."""
    evidence: List[EvidenceItem] = []
    t_str = event.event_time_utc.strftime("%Y%m%d%H%M%S")

    for m in event.measurements:
        if not isinstance(m.value, (int, float)) or isinstance(m.value, bool):
            continue
        if m.signal_id in STATIC_METADATA_SIGNALS:
            continue
        val = float(m.value)
        key = m.signal_id if m.phase is None else f"{m.signal_id}_{m.phase}"

        hist = history_buffer.get(key, [])

        # 1. Rate-of-Change / Impossible Step (e.g. for OTI)
        if m.signal_id in ("oti_degc", "top_oil_temperature") and hist:
            last_t, last_val = hist[-1]
            dt_minutes = max(0.1, (event.event_time_utc - last_t).total_seconds() / 60.0)
            step_change = abs(val - last_val)
            roc = step_change / dt_minutes
            max_step = getattr(thresholds, "oti_max_step_degc", 10.0)
            if roc > thresholds.oti_max_rate_degc_per_min or step_change > max_step:
                ev_id = f"ev_{event.asset_id}_plaus_roc_{key}_{t_str}"
                evidence.append(
                    EvidenceItem(
                        evidence_id=ev_id,
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.SENSOR_PLAUSIBILITY,
                        detector_id="DET_PLAUS_RATE_OF_CHANGE",
                        observed_value=round(roc, 2),
                        expected_value=f"<= {thresholds.oti_max_rate_degc_per_min} degC/min",
                        unit="degC/min",
                        threshold_or_band=f"<= {thresholds.oti_max_rate_degc_per_min}",
                        direction="HIGH",
                        severity=0.85,
                        confidence=0.90,
                        input_lineage=[m.signal_id],
                        reason_codes=["IMPOSSIBLE_TEMPERATURE_RATE_OF_CHANGE"],
                        hypothesis_codes=["SENSOR_TRANSIENT_SPIKE", "METER_INTERMITTENT_GLITCH"],
                    )
                )

        # 2. Frozen / Flatline Sensor
        req_steps = thresholds.stuck_consecutive_steps
        if m.signal_id in ("oti_degc", "top_oil_temperature", "ambient_temperature"):
            req_steps = max(thresholds.stuck_consecutive_steps, getattr(thresholds, "temp_flatline_min_steps", 4))
        if len(hist) >= req_steps - 1:
            recent_vals = [h[1] for h in hist[-(req_steps - 1):]] + [val]
            if len(recent_vals) >= req_steps and len(set(recent_vals)) == 1 and val != 0.0:
                ev_id = f"ev_{event.asset_id}_plaus_stuck_{key}_{t_str}"
                evidence.append(
                    EvidenceItem(
                        evidence_id=ev_id,
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.SENSOR_PLAUSIBILITY,
                        detector_id="DET_PLAUS_FROZEN_SENSOR",
                        observed_value=val,
                        expected_value="Varying",
                        unit=m.unit_ucum,
                        threshold_or_band=f"{req_steps} identical readings",
                        direction="FLATLINE",
                        severity=0.60,
                        confidence=0.85,
                        input_lineage=[m.signal_id],
                        reason_codes=["SENSOR_FLATLINE_DETECTED"],
                        hypothesis_codes=["STUCK_ANALOG_INPUT", "DAUGHTERBOARD_ADC_LOCKUP"],
                    )
                )

    return evidence


def detect_thermal_limits(
    event: CanonicalEvent,
    thresholds: AnomalyDetectorThresholds = DEFAULT_DETECTOR_THRESHOLDS,
) -> List[EvidenceItem]:
    """Detect direct physical top-oil and differential temperature limit exceedance."""
    evidence: List[EvidenceItem] = []
    t_str = event.event_time_utc.strftime("%Y%m%d%H%M%S")

    meas_map: Dict[str, float] = {}
    for m in event.measurements:
        if isinstance(m.value, (int, float)) and not isinstance(m.value, bool):
            meas_map[m.signal_id] = float(m.value)

    t_oil = meas_map.get("oti_degc") or meas_map.get("top_oil_temperature")
    t_amb = meas_map.get("ambient_temperature")

    # 1. Absolute Top-Oil Limits
    if t_oil is not None:
        if t_oil >= thresholds.oti_critical_degc:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_thlimit_crit_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.THERMAL_LIMIT,
                    detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
                    observed_value=round(t_oil, 2),
                    expected_value=f"< {thresholds.oti_warning_degc}",
                    unit="Cel",
                    threshold_or_band=f">= {thresholds.oti_critical_degc}",
                    direction="HIGH",
                    severity=0.95,
                    confidence=1.0,
                    input_lineage=["oti_degc"],
                    reason_codes=["TOP_OIL_CRITICAL_LIMIT_EXCEEDED"],
                    hypothesis_codes=["SEVERE_OVERLOAD", "COOLING_FAILURE", "SEVERE_INTERNAL_FAULT"],
                )
            )
        elif t_oil >= thresholds.oti_warning_degc:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_thlimit_warn_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.THERMAL_LIMIT,
                    detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
                    observed_value=round(t_oil, 2),
                    expected_value=f"< {thresholds.oti_warning_degc}",
                    unit="Cel",
                    threshold_or_band=f">= {thresholds.oti_warning_degc}",
                    direction="HIGH",
                    severity=warning_band_severity(t_oil, thresholds.oti_warning_degc, thresholds.oti_critical_degc),
                    confidence=1.0,
                    input_lineage=["oti_degc"],
                    reason_codes=["TOP_OIL_WARNING_LIMIT_EXCEEDED"],
                    hypothesis_codes=["HIGH_LOADING", "AMBIENT_HEATWAVE", "RADIATOR_FOULING"],
                )
            )

    # 2. Temperature Rise Over Ambient Limits
    if t_oil is not None and t_amb is not None:
        rise = t_oil - t_amb
        if rise >= thresholds.rise_critical_degc:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_thrise_crit_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.THERMAL_LIMIT,
                    detector_id="DET_THERMAL_LIMIT_RISE",
                    observed_value=round(rise, 2),
                    expected_value=f"< {thresholds.rise_warning_degc}",
                    unit="Cel",
                    threshold_or_band=f">= {thresholds.rise_critical_degc}",
                    direction="HIGH",
                    severity=0.90,
                    confidence=0.95,
                    input_lineage=["oti_degc", "ambient_temperature"],
                    reason_codes=["TOP_OIL_RISE_CRITICAL_EXCEEDED"],
                    hypothesis_codes=["COOLING_DEGRADATION", "EXTREME_WINDING_LOSSES"],
                )
            )
        elif rise >= thresholds.rise_warning_degc:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_thrise_warn_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.THERMAL_LIMIT,
                    detector_id="DET_THERMAL_LIMIT_RISE",
                    observed_value=round(rise, 2),
                    expected_value=f"< {thresholds.rise_warning_degc}",
                    unit="Cel",
                    threshold_or_band=f">= {thresholds.rise_warning_degc}",
                    direction="HIGH",
                    severity=warning_band_severity(rise, thresholds.rise_warning_degc, thresholds.rise_critical_degc),
                    confidence=0.95,
                    input_lineage=["oti_degc", "ambient_temperature"],
                    reason_codes=["TOP_OIL_RISE_WARNING_EXCEEDED"],
                    hypothesis_codes=["COOLING_MARGIN_REDUCTION", "HEAVY_SUSTAINED_LOAD"],
                )
            )

    return evidence


def detect_thermal_deviation(
    event: CanonicalEvent,
    thermal_output: Optional[ThermalRuntimeOutput] = None,
    qualification: Optional[ThermalModelQualification] = None,
) -> List[EvidenceItem]:
    """Detect thermal model residual deviations and CUSUM drift with strict qualification gating."""
    if thermal_output is None:
        return []

    evidence: List[EvidenceItem] = []
    t_str = event.event_time_utc.strftime("%Y%m%d%H%M%S")

    # Respect Authority Gates: If residual anomaly detection is not qualified, do not emit operational alarms
    is_res_qual = (
        qualification is not None
        and qualification.residual_anomaly_qualification == QualificationStatus.QUALIFIED
    )
    is_cusum_qual = (
        qualification is not None
        and qualification.cusum_qualification == QualificationStatus.QUALIFIED
    )

    if thermal_output.cusum_alarm_active:
        cusum_val = thermal_output.cusum_pos if thermal_output.cusum_pos > 0 else thermal_output.cusum_neg
        direction_str = "POSITIVE_SHIFT" if thermal_output.cusum_pos > 0 else "NEGATIVE_SHIFT"

        if is_cusum_qual and is_res_qual:
            # Fully qualified operational evidence
            # Distinguish positive overheating drift from negative undercooling / model bias
            if direction_str == "POSITIVE_SHIFT":
                sev = 0.75
            else:
                # Negative residual drift: oil cooler than expected is mild model bias / undercooling, capped at 0.30 WATCH
                sev = min(0.30, 0.20 + 0.10 * min(1.0, max(0.0, (abs(cusum_val) - 4.5) / 4.5)))

            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_thdev_cusum_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.THERMAL_DEVIATION,
                    detector_id="DET_THERMAL_CUSUM_DRIFT",
                    observed_value=round(cusum_val, 2),
                    expected_value=0.0,
                    unit="sigma",
                    threshold_or_band="CUSUM h decision limit",
                    direction=direction_str,
                    severity=sev,
                    confidence=0.85,
                    input_lineage=["oti_degc", "ambient_temperature", "apparent_power"],
                    reason_codes=["PERSISTENT_THERMAL_RESIDUAL_DRIFT"],
                    hypothesis_codes=["THERMAL_MODEL_RESIDUAL_BIAS", "COOLING_EFFICIENCY_SHIFT"],
                )
            )
        else:
            # Shadow / Unqualified descriptive evidence (Tripura state)
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_thdev_shadow_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.THERMAL_DEVIATION,
                    detector_id="DET_THERMAL_SHADOW_DESCRIPTIVE",
                    observed_value=round(cusum_val, 2),
                    expected_value=0.0,
                    unit="sigma",
                    threshold_or_band="Shadow Exploratory",
                    direction=direction_str,
                    severity=0.30,  # Suppressed severity for shadow evaluation
                    confidence=0.40,  # Low confidence reflecting unqualified status
                    input_lineage=["oti_degc", "ambient_temperature"],
                    reason_codes=["SHADOW_THERMAL_CUSUM_EXCURSION"],
                    hypothesis_codes=["UNQUALIFIED_SHADOW_EVIDENCE", "MODEL_PARAMETER_UNCERTAINTY"],
                )
            )

    return evidence


def detect_loading(
    event: CanonicalEvent,
    derived: Optional[DerivedFeatures] = None,
    profile: Optional[AssetProfile] = None,
    thresholds: AnomalyDetectorThresholds = DEFAULT_DETECTOR_THRESHOLDS,
) -> List[EvidenceItem]:
    """Detect transformer loading and relative capacity overload excursions."""
    evidence: List[EvidenceItem] = []
    t_str = event.event_time_utc.strftime("%Y%m%d%H%M%S")

    if derived is not None and derived.relative_load_index is not None:
        u = derived.relative_load_index
        if u >= thresholds.load_u_critical:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_load_crit_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.LOADING,
                    detector_id="DET_LOAD_RELATIVE_INDEX",
                    observed_value=round(u * 100.0, 1),
                    expected_value=f"< {thresholds.load_u_warning * 100.0}%",
                    unit="%",
                    threshold_or_band=f">= {thresholds.load_u_critical * 100.0}%",
                    direction="HIGH",
                    severity=0.90,
                    confidence=0.95,
                    input_lineage=["apparent_power_total", "current_l1", "current_l2", "current_l3"],
                    reason_codes=["CRITICAL_OVERLOAD_EXCEEDED"],
                    hypothesis_codes=["SYSTEM_PEAK_DEMAND", "LOAD_TRANSFERRED_FROM_ADJACENT_FEEDER"],
                )
            )
        elif u >= thresholds.load_u_warning:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_load_warn_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.LOADING,
                    detector_id="DET_LOAD_RELATIVE_INDEX",
                    observed_value=round(u * 100.0, 1),
                    expected_value=f"< {thresholds.load_u_warning * 100.0}%",
                    unit="%",
                    threshold_or_band=f">= {thresholds.load_u_warning * 100.0}%",
                    direction="HIGH",
                    severity=warning_band_severity(u, thresholds.load_u_warning, thresholds.load_u_critical),
                    confidence=0.95,
                    input_lineage=["apparent_power_total"],
                    reason_codes=["NAMEPLATE_CAPACITY_OVERLOAD"],
                    hypothesis_codes=["HIGH_FEEDER_LOADING"],
                )
            )

    return evidence


def detect_phase_neutral(
    event: CanonicalEvent,
    derived: Optional[DerivedFeatures] = None,
    thresholds: AnomalyDetectorThresholds = DEFAULT_DETECTOR_THRESHOLDS,
) -> List[EvidenceItem]:
    """Detect current imbalance (% IUB) and neutral current ratio excursions."""
    evidence: List[EvidenceItem] = []
    t_str = event.event_time_utc.strftime("%Y%m%d%H%M%S")

    if derived is None:
        return evidence

    # 1. Current Imbalance (% IUB)
    if derived.current_magnitude_imbalance_pct is not None:
        iub = derived.current_magnitude_imbalance_pct
        if iub >= thresholds.current_imbalance_critical_pct:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_ph_iub_crit_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.PHASE_OR_NEUTRAL,
                    detector_id="DET_PHASE_CURRENT_IMBALANCE",
                    observed_value=round(iub, 2),
                    expected_value=f"< {thresholds.current_imbalance_warning_pct}%",
                    unit="%",
                    threshold_or_band=f">= {thresholds.current_imbalance_critical_pct}%",
                    direction="HIGH",
                    severity=0.90,
                    confidence=0.90,
                    input_lineage=["current_l1", "current_l2", "current_l3"],
                    reason_codes=["CURRENT_IMBALANCE_CRITICAL_EXCEEDED"],
                    hypothesis_codes=["UNBALANCED_SINGLE_PHASE_LOADS", "LOOSE_TERMINAL_CONNECTION", "ASYMMETRIC_FEEDER_DEMAND"],
                )
            )
        elif iub >= thresholds.current_imbalance_warning_pct:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_ph_iub_warn_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.PHASE_OR_NEUTRAL,
                    detector_id="DET_PHASE_CURRENT_IMBALANCE",
                    observed_value=round(iub, 2),
                    expected_value=f"< {thresholds.current_imbalance_warning_pct}%",
                    unit="%",
                    threshold_or_band=f">= {thresholds.current_imbalance_warning_pct}%",
                    direction="HIGH",
                    severity=warning_band_severity(
                        iub, thresholds.current_imbalance_warning_pct, thresholds.current_imbalance_critical_pct
                    ),
                    confidence=0.90,
                    input_lineage=["current_l1", "current_l2", "current_l3"],
                    reason_codes=["CURRENT_IMBALANCE_WARNING_EXCEEDED"],
                    hypothesis_codes=["SINGLE_PHASE_LOAD_ASYMMETRY"],
                )
            )

    # 2. Neutral Current Ratio
    if derived.neutral_current_ratio is not None:
        in_ratio = derived.neutral_current_ratio
        if in_ratio >= thresholds.neutral_ratio_critical:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_ph_neutral_crit_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.PHASE_OR_NEUTRAL,
                    detector_id="DET_NEUTRAL_CURRENT_RATIO",
                    observed_value=round(in_ratio, 2),
                    expected_value=f"< {thresholds.neutral_ratio_warning}",
                    unit="ratio",
                    threshold_or_band=f">= {thresholds.neutral_ratio_critical}",
                    direction="HIGH",
                    severity=0.85,
                    confidence=0.90,
                    input_lineage=["neutral_current", "current_l1", "current_l2", "current_l3"],
                    reason_codes=["EXCESSIVE_NEUTRAL_CURRENT_RATIO"],
                    hypothesis_codes=["HIGH_NEUTRAL_RETURN", "ZERO_SEQUENCE_CURRENT_INJECTION", "POOR_GROUNDING"],
                )
            )
        elif in_ratio >= thresholds.neutral_ratio_warning:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_ph_neutral_warn_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.PHASE_OR_NEUTRAL,
                    detector_id="DET_NEUTRAL_CURRENT_RATIO",
                    observed_value=round(in_ratio, 2),
                    expected_value=f"< {thresholds.neutral_ratio_warning}",
                    unit="ratio",
                    threshold_or_band=f">= {thresholds.neutral_ratio_warning}",
                    direction="HIGH",
                    severity=warning_band_severity(in_ratio, thresholds.neutral_ratio_warning, thresholds.neutral_ratio_critical),
                    confidence=0.90,
                    input_lineage=["neutral_current"],
                    reason_codes=["NEUTRAL_CURRENT_RATIO_ELEVATED"],
                    hypothesis_codes=["PHASE_LOAD_UNBALANCE"],
                )
            )

    return evidence


def detect_voltage_pf_frequency(
    event: CanonicalEvent,
    derived: Optional[DerivedFeatures] = None,
    profile: Optional[AssetProfile] = None,
    thresholds: AnomalyDetectorThresholds = DEFAULT_DETECTOR_THRESHOLDS,
) -> List[EvidenceItem]:
    """Detect voltage imbalance (% VUB), low power factor, undervoltage, and overvoltage."""
    evidence: List[EvidenceItem] = []
    t_str = event.event_time_utc.strftime("%Y%m%d%H%M%S")

    # 1. Voltage Imbalance (% VUB)
    if derived is not None and derived.voltage_magnitude_imbalance_pct is not None:
        vub = derived.voltage_magnitude_imbalance_pct
        if vub >= thresholds.voltage_imbalance_critical_pct:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_vpf_vub_crit_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
                    detector_id="DET_VOLTAGE_IMBALANCE",
                    observed_value=round(vub, 2),
                    expected_value=f"< {thresholds.voltage_imbalance_warning_pct}%",
                    unit="%",
                    threshold_or_band=f">= {thresholds.voltage_imbalance_critical_pct}%",
                    direction="HIGH",
                    severity=0.85,
                    confidence=0.95,
                    input_lineage=["voltage_v1", "voltage_v2", "voltage_v3"],
                    reason_codes=["VOLTAGE_IMBALANCE_CRITICAL_EXCEEDED"],
                    hypothesis_codes=["UPSTREAM_GRID_UNBALANCE", "FEEDER_IMPEDANCE_ASYMMETRY"],
                )
            )
        elif vub >= thresholds.voltage_imbalance_warning_pct:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_vpf_vub_warn_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
                    detector_id="DET_VOLTAGE_IMBALANCE",
                    observed_value=round(vub, 2),
                    expected_value=f"< {thresholds.voltage_imbalance_warning_pct}%",
                    unit="%",
                    threshold_or_band=f">= {thresholds.voltage_imbalance_warning_pct}%",
                    direction="HIGH",
                    severity=warning_band_severity(
                        vub, thresholds.voltage_imbalance_warning_pct, thresholds.voltage_imbalance_critical_pct
                    ),
                    confidence=0.95,
                    input_lineage=["voltage_v1", "voltage_v2", "voltage_v3"],
                    reason_codes=["VOLTAGE_IMBALANCE_WARNING_EXCEEDED"],
                    hypothesis_codes=["GRID_SUPPLY_UNBALANCE"],
                )
            )

    # 2. Power Factor (lower is worse)
    if derived is not None and derived.power_factor_derived is not None:
        pf = derived.power_factor_derived
        if pf <= thresholds.pf_critical:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_vpf_pf_crit_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
                    detector_id="DET_LOW_POWER_FACTOR",
                    observed_value=round(pf, 3),
                    expected_value=f">= {thresholds.pf_warning}",
                    unit="dimensionless",
                    threshold_or_band=f"<= {thresholds.pf_critical}",
                    direction="LOW",
                    severity=0.80,
                    confidence=0.95,
                    input_lineage=["active_power_total", "apparent_power_total"],
                    reason_codes=["CRITICAL_LOW_POWER_FACTOR"],
                    hypothesis_codes=["HEAVY_INDUCTIVE_LOAD", "INADEQUATE_VAR_COMPENSATION"],
                )
            )
        elif pf <= thresholds.pf_warning:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"ev_{event.asset_id}_vpf_pf_warn_{t_str}",
                    asset_id=event.asset_id,
                    event_time_utc=event.event_time_utc,
                    category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
                    detector_id="DET_LOW_POWER_FACTOR",
                    observed_value=round(pf, 3),
                    expected_value=f">= {thresholds.pf_warning}",
                    unit="dimensionless",
                    threshold_or_band=f"<= {thresholds.pf_warning}",
                    direction="LOW",
                    severity=warning_band_severity(pf, thresholds.pf_warning, thresholds.pf_critical),
                    confidence=0.95,
                    input_lineage=["active_power_total", "apparent_power_total"],
                    reason_codes=["LOW_POWER_FACTOR_WARNING"],
                    hypothesis_codes=["INDUCTIVE_LOADS_ONLINE"],
                )
            )

    # 3. Direct Phase Undervoltage / Overvoltage
    v_nom = thresholds.v_nominal_v
    if profile is not None:
        if getattr(profile, "rated_voltage_lv_v", None) is not None:
            v_nom = float(profile.rated_voltage_lv_v)
        elif hasattr(profile, "fields") and "nominal_voltage_v" in profile.fields:
            v_nom = float(profile.fields["nominal_voltage_v"].value)
        elif hasattr(profile, "fields") and "rated_voltage_lv_v" in profile.fields:
            v_nom = float(profile.fields["rated_voltage_lv_v"].value)
        elif getattr(profile, "nominal_voltage_v", None) is not None:
            v_nom = float(profile.nominal_voltage_v)

    v_min_thresh = v_nom * thresholds.undervoltage_ratio
    v_max_thresh = v_nom * thresholds.overvoltage_ratio

    for m in event.measurements:
        if m.signal_id in ("voltage_v1", "voltage_v2", "voltage_v3", "voltage_l1_n", "voltage_l2_n", "voltage_l3_n"):
            if isinstance(m.value, (int, float)) and not isinstance(m.value, bool):
                v_val = float(m.value)
                if v_val < v_min_thresh and v_val > 10.0:  # Ignore de-energized (<10V)
                    evidence.append(
                        EvidenceItem(
                            evidence_id=f"ev_{event.asset_id}_vpf_undervoltage_{m.signal_id}_{t_str}",
                            asset_id=event.asset_id,
                            event_time_utc=event.event_time_utc,
                            category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
                            detector_id="DET_VOLTAGE_SAG_OR_UNDERVOLTAGE",
                            observed_value=round(v_val, 1),
                            expected_value=f">= {v_min_thresh:.1f} V",
                            unit="V",
                            threshold_or_band=f"< {v_min_thresh:.1f} V",
                            direction="LOW",
                            severity=0.65,
                            confidence=0.95,
                            input_lineage=[m.signal_id],
                            reason_codes=["PHASE_UNDERVOLTAGE_DETECTED"],
                            hypothesis_codes=["DISTRIBUTION_LINE_SAG", "HEAVY_DOWNSTREAM_DRAW"],
                        )
                    )
                elif v_val > v_max_thresh:
                    evidence.append(
                        EvidenceItem(
                            evidence_id=f"ev_{event.asset_id}_vpf_overvoltage_{m.signal_id}_{t_str}",
                            asset_id=event.asset_id,
                            event_time_utc=event.event_time_utc,
                            category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
                            detector_id="DET_VOLTAGE_SWELL_OR_OVERVOLTAGE",
                            observed_value=round(v_val, 1),
                            expected_value=f"<= {v_max_thresh:.1f} V",
                            unit="V",
                            threshold_or_band=f"> {v_max_thresh:.1f} V",
                            direction="HIGH",
                            severity=0.70,
                            confidence=0.95,
                            input_lineage=[m.signal_id],
                            reason_codes=["PHASE_OVERVOLTAGE_DETECTED"],
                            hypothesis_codes=["FERRANTI_EFFECT", "TAP_CHANGER_MISPOSITION"],
                        )
                    )

    return evidence


def detect_protection_oil_status(
    event: CanonicalEvent,
    profile: Optional[AssetProfile] = None,
    history_buffer: Optional[Dict[str, List[Tuple[datetime, float]]]] = None,
    thresholds: AnomalyDetectorThresholds = DEFAULT_DETECTOR_THRESHOLDS,
) -> List[EvidenceItem]:
    """Detect discrete protection contacts, breaker/fuse operations, oil level trends, and tank pressure."""
    evidence: List[EvidenceItem] = []
    t_str = event.event_time_utc.strftime("%Y%m%d%H%M%S")

    # Asset applicability flags (conservator assets lack pressure sensors; sealed assets lack oil gauges)
    has_oil_gauge = (profile.has_oil_level_gauge and profile.tank_type != "SEALED_CORRUGATED") if profile else True
    has_pressure = (
        bool(profile.has_pressure_sensor or profile.tank_type == "SEALED_CORRUGATED")
        if profile
        else False
    )


    for m in event.measurements:
        s_id = m.signal_id.lower()
        val = m.value

        # 1. Winding Temperature Trip / Alarm (WTI)
        if s_id in ("wti", "winding_temp_alarm_contact", "wti_alarm"):
            if val in (1, 1.0, "1", True):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_wti_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PROT_WTI_CONTACT",
                        observed_value=1,
                        expected_value=0,
                        unit="binary",
                        threshold_or_band="1 (Alarm/Trip)",
                        direction="CONTACT_CLOSED",
                        severity=1.0,  # Maximum Critical Severity
                        confidence=1.0,  # Direct Hardware Contact
                        input_lineage=[m.signal_id],
                        reason_codes=["WTI_PROTECTION_CONTACT_TRIPPED"],
                        hypothesis_codes=["SEVERE_INTERNAL_WINDING_OVERHEATING", "COOLING_FAILURE"],
                    )
                )

        # 2. Top-Oil Temperature Alarm / Trip (OTI_A, OTI_T)
        elif s_id in ("oti_t", "oil_temp_trip_flag", "oti_trip", "oti_trip_contact"):
            if val in (1, 1.0, "1", True):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_oti_trip_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PROT_OTI_TRIP",
                        observed_value=1,
                        expected_value=0,
                        unit="binary",
                        threshold_or_band="1 (Trip)",
                        direction="CONTACT_CLOSED",
                        severity=1.0,
                        confidence=1.0,
                        input_lineage=[m.signal_id],
                        reason_codes=["OTI_PROTECTION_TRIP_CONTACT_CLOSED"],
                        hypothesis_codes=["TOP_OIL_CRITICAL_OVERHEAT_TRIP"],
                    )
                )
        elif s_id in ("oti_a", "oil_temp_alarm_flag", "oti_alarm", "oti_alarm_contact"):
            if val in (1, 1.0, "1", True):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_oti_alarm_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PROT_OTI_ALARM",
                        observed_value=1,
                        expected_value=0,
                        unit="binary",
                        threshold_or_band="1 (Alarm)",
                        direction="CONTACT_CLOSED",
                        severity=0.75,
                        confidence=1.0,
                        input_lineage=[m.signal_id],
                        reason_codes=["OTI_PROTECTION_ALARM_CONTACT_CLOSED"],
                        hypothesis_codes=["HIGH_TOP_OIL_TEMPERATURE"],
                    )
                )

        # 3. Breaker / Fuse Protection Trips (Extra C)
        elif s_id in ("lv_breaker_trip", "lv_breaker_trip_contact"):
            if val in (1, 1.0, "1", True):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_lv_trip_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PROT_LV_BREAKER_TRIP",
                        observed_value=1,
                        expected_value=0,
                        unit="binary",
                        threshold_or_band="1 (Trip)",
                        direction="CONTACT_CLOSED",
                        severity=1.0,
                        confidence=1.0,
                        input_lineage=[m.signal_id],
                        reason_codes=["LV_CIRCUIT_BREAKER_TRIPPED"],
                        hypothesis_codes=["THROUGH_FAULT_INTERRUPTED", "DOWNSTREAM_SHORT_CIRCUIT"],
                    )
                )
        elif s_id in ("lv_breaker_closed", "52a_status"):
            if val in (0, 0.0, "0", False) or str(val).lower() in ("open", "tripped", "false", "0"):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_lv_trip_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PROT_LV_BREAKER_TRIP",
                        observed_value=0,
                        expected_value=1,
                        unit="binary",
                        threshold_or_band="0 (Open/Trip)",
                        direction="BREAKER_OPEN",
                        severity=1.0,
                        confidence=1.0,
                        input_lineage=[m.signal_id],
                        reason_codes=["LV_CIRCUIT_BREAKER_OPEN_OR_TRIPPED"],
                        hypothesis_codes=["THROUGH_FAULT_INTERRUPTED", "DOWNSTREAM_SHORT_CIRCUIT"],
                    )
                )
        elif s_id in ("hv_fuse_operated", "hv_fuse_trip"):
            if val in (1, 1.0, "1", True):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_hv_fuse_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PROT_HV_FUSE_OPERATED",
                        observed_value=1,
                        expected_value=0,
                        unit="binary",
                        threshold_or_band="1 (Operated)",
                        direction="CONTACT_CLOSED",
                        severity=1.0,
                        confidence=1.0,
                        input_lineage=[m.signal_id],
                        reason_codes=["HV_EXPULSION_FUSE_OPERATED"],
                        hypothesis_codes=["TRANSFORMER_INTERNAL_OR_FEEDER_FAULT", "BACKUP_CLEARING"],
                    )
                )

        # 4. Magnetic Oil Gauge / Low Oil Alarm Contact
        elif s_id in ("mog_a", "magnetic_oil_gauge_alarm_flag", "mog_alarm", "oil_level_low_alarm"):
            if val in (1, 1.0, "1", True):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_mog_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PROT_MOG_ALARM",
                        observed_value=1,
                        expected_value=0,
                        unit="binary",
                        threshold_or_band="1 (Low Oil Alarm)",
                        direction="CONTACT_CLOSED",
                        severity=0.85,
                        confidence=1.0,
                        input_lineage=[m.signal_id],
                        reason_codes=["LOW_OIL_LEVEL_ALARM_CONTACT_CLOSED"],
                        hypothesis_codes=["INSULATING_OIL_LEAKAGE", "CONSERVATOR_TANK_EMPTY"],
                    )
                )

        # 5. Oil Level Indicator & Trend Monitoring (Extra A)
        elif s_id in ("oli", "oil_level_pct", "oil_level", "oil_level_percent") and has_oil_gauge:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                oli_val = float(val)
                if oli_val <= thresholds.oil_level_critical_pct:
                    evidence.append(
                        EvidenceItem(
                            evidence_id=f"ev_{event.asset_id}_prot_oli_crit_{t_str}",
                            asset_id=event.asset_id,
                            event_time_utc=event.event_time_utc,
                            category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                            detector_id="DET_OIL_LEVEL_INDICATOR",
                            observed_value=round(oli_val, 1),
                            expected_value=f"> {thresholds.oil_level_warning_pct}%",
                            unit="%",
                            threshold_or_band=f"<= {thresholds.oil_level_critical_pct}%",
                            direction="LOW",
                            severity=0.95,
                            confidence=0.95,
                            input_lineage=[m.signal_id],
                            reason_codes=["CRITICAL_LOW_OIL_LEVEL"],
                            hypothesis_codes=["SEVERE_TANK_LEAKAGE", "RADIATOR_VALVE_BREACH"],
                        )
                    )
                elif oli_val <= thresholds.oil_level_warning_pct:
                    evidence.append(
                        EvidenceItem(
                            evidence_id=f"ev_{event.asset_id}_prot_oli_warn_{t_str}",
                            asset_id=event.asset_id,
                            event_time_utc=event.event_time_utc,
                            category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                            detector_id="DET_OIL_LEVEL_INDICATOR",
                            observed_value=round(oli_val, 1),
                            expected_value=f"> {thresholds.oil_level_warning_pct}%",
                            unit="%",
                            threshold_or_band=f"<= {thresholds.oil_level_warning_pct}%",
                            direction="LOW",
                            severity=warning_band_severity(
                                oli_val, thresholds.oil_level_warning_pct, thresholds.oil_level_critical_pct
                            ),
                            confidence=0.95,
                            input_lineage=[m.signal_id],
                            reason_codes=["LOW_OIL_LEVEL_WARNING"],
                            hypothesis_codes=["OIL_SEEPAGE", "TEMPERATURE_CONTRACTION"],
                        )
                    )

        elif s_id in ("oil_level_trend_pct_per_day",) and has_oil_gauge:
            # Suppress trend-based leak conclusions if measurement quality is BAD
            if m.quality and m.quality.severity == QualitySeverity.BAD:
                continue
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                trend_val = float(val)
                if trend_val <= thresholds.oil_leak_trend_threshold_pct_per_day:
                    sev = 0.75
                    conf = 0.85
                    evidence.append(
                        EvidenceItem(
                            evidence_id=f"ev_{event.asset_id}_prot_oil_trend_{t_str}",
                            asset_id=event.asset_id,
                            event_time_utc=event.event_time_utc,
                            category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                            detector_id="DET_OIL_LEVEL_DECLINING_TREND",
                            observed_value=round(trend_val, 3),
                            expected_value=f"> {thresholds.oil_leak_trend_threshold_pct_per_day} %/day",
                            unit="percent/day",
                            threshold_or_band=f"<= {thresholds.oil_leak_trend_threshold_pct_per_day} %/day",
                            direction="LOW",
                            severity=sev,
                            confidence=conf,
                            input_lineage=[m.signal_id],
                            reason_codes=["SUSPECTED_OIL_LOSS_TREND", "INSPECTION_REQUIRED"],
                            hypothesis_codes=["SUSPECTED_SLOW_OIL_LEAK", "VALVE_SEEPAGE"],
                        )
                    )

        # 6. Sealed-Tank Pressure Monitoring (Extra B)
        elif s_id in ("prd_operated", "pressure_relief_operated") and has_pressure:
            if val in (1, 1.0, "1", True):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_prd_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PRESSURE_RELIEF_OPERATED",
                        observed_value=1,
                        expected_value=0,
                        unit="binary",
                        threshold_or_band="1 (Operated)",
                        direction="CONTACT_CLOSED",
                        severity=1.0,
                        confidence=1.0,
                        input_lineage=[m.signal_id],
                        reason_codes=["PRESSURE_RELIEF_DEVICE_OPERATED"],
                        hypothesis_codes=["EXCESS_INTERNAL_PRESSURE", "TANK_PRESSURE_RELIEF_DISCHARGE"],
                    )
                )

        elif s_id in ("pressure_alarm", "tank_pressure_alarm") and has_pressure:
            if val in (1, 1.0, "1", True):
                evidence.append(
                    EvidenceItem(
                        evidence_id=f"ev_{event.asset_id}_prot_pressure_alarm_{t_str}",
                        asset_id=event.asset_id,
                        event_time_utc=event.event_time_utc,
                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                        detector_id="DET_PRESSURE_ALARM_CONTACT",
                        observed_value=1,
                        expected_value=0,
                        unit="binary",
                        threshold_or_band="1 (Alarm)",
                        direction="CONTACT_CLOSED",
                        severity=0.85,
                        confidence=1.0,
                        input_lineage=[m.signal_id],
                        reason_codes=["TANK_PRESSURE_ALARM_CONTACT_CLOSED"],
                        hypothesis_codes=["HIGH_INTERNAL_TANK_PRESSURE"],
                    )
                )

        elif s_id in ("tank_pressure_kpa_g", "tank_pressure") and has_pressure:
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                p_kpa = float(val)
                if not math.isfinite(p_kpa):
                    continue

                # Check history buffer for analog pressure persistence
                p_history = (
                    history_buffer.get("tank_pressure_kpa_g")
                    or history_buffer.get("tank_pressure")
                    or []
                ) if history_buffer else []
                has_prior = len(p_history) >= 1
                last_p = p_history[-1][1] if has_prior else None

                if p_kpa >= thresholds.tank_pressure_warning_kpa_g:
                    is_transient = (last_p is not None and last_p < thresholds.tank_pressure_warning_kpa_g)
                    if is_transient:
                        # Isolated / candidate excursion from established normal baseline
                        evidence.append(
                            EvidenceItem(
                                evidence_id=f"ev_{event.asset_id}_prot_p_transient_{t_str}",
                                asset_id=event.asset_id,
                                event_time_utc=event.event_time_utc,
                                category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                                detector_id="DET_PRESSURE_HIGH_TRANSIENT",
                                observed_value=round(p_kpa, 1),
                                expected_value=f"< {thresholds.tank_pressure_warning_kpa_g} kPa(g)",
                                unit="kPa",
                                threshold_or_band=f"TRANSIENT_EXCURSION (>={thresholds.tank_pressure_warning_kpa_g} kPa(g))",
                                direction="TRANSIENT_HIGH",
                                severity=0.25,
                                confidence=0.70,
                                input_lineage=[m.signal_id],
                                reason_codes=["ISOLATED_PRESSURE_EXCURSION"],
                                hypothesis_codes=["TRANSIENT_PRESSURE_PULSE", "THERMAL_SWITCHING_PEAK"],
                            )
                        )
                    else:
                        # Genuine sustained abnormal high pressure (or cold-start threshold violation)
                        evidence.append(
                            EvidenceItem(
                                evidence_id=f"ev_{event.asset_id}_prot_p_high_{t_str}",
                                asset_id=event.asset_id,
                                event_time_utc=event.event_time_utc,
                                category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                                detector_id="DET_PRESSURE_HIGH_ALARM",
                                observed_value=round(p_kpa, 1),
                                expected_value=f"< {thresholds.tank_pressure_warning_kpa_g} kPa(g)",
                                unit="kPa",
                                threshold_or_band=f">= {thresholds.tank_pressure_warning_kpa_g} kPa(g)",
                                direction="HIGH",
                                severity=0.85,
                                confidence=0.95,
                                input_lineage=[m.signal_id],
                                reason_codes=["SEALED_TANK_HIGH_PRESSURE"],
                                hypothesis_codes=["HEAVY_THERMAL_EXPANSION", "INTERNAL_GAS_ACCUMULATION"],
                            )
                        )
                elif p_kpa <= thresholds.tank_pressure_low_kpa_g:
                    is_low_transient = (last_p is not None and last_p > thresholds.tank_pressure_low_kpa_g)
                    if is_low_transient:
                        # Isolated / candidate low excursion from established normal baseline
                        evidence.append(
                            EvidenceItem(
                                evidence_id=f"ev_{event.asset_id}_prot_p_low_transient_{t_str}",
                                asset_id=event.asset_id,
                                event_time_utc=event.event_time_utc,
                                category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                                detector_id="DET_PRESSURE_LOW_TRANSIENT",
                                observed_value=round(p_kpa, 1),
                                expected_value=f"> {thresholds.tank_pressure_low_kpa_g} kPa(g)",
                                unit="kPa",
                                threshold_or_band=f"TRANSIENT_EXCURSION (<={thresholds.tank_pressure_low_kpa_g} kPa(g))",
                                direction="TRANSIENT_LOW",
                                severity=0.20,
                                confidence=0.70,
                                input_lineage=[m.signal_id],
                                reason_codes=["ISOLATED_LOW_PRESSURE_EXCURSION"],
                                hypothesis_codes=["TRANSIENT_THERMAL_CONTRACTION", "CYCLIC_LOAD_DROP"],
                            )
                        )
                    else:
                        # Genuine sustained abnormal low pressure (or cold-start depressurization)
                        evidence.append(
                            EvidenceItem(
                                evidence_id=f"ev_{event.asset_id}_prot_p_low_{t_str}",
                                asset_id=event.asset_id,
                                event_time_utc=event.event_time_utc,
                                category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                                detector_id="DET_PRESSURE_LOW_ALARM",
                                observed_value=round(p_kpa, 1),
                                expected_value=f"> {thresholds.tank_pressure_low_kpa_g} kPa(g)",
                                unit="kPa",
                                threshold_or_band=f"<= {thresholds.tank_pressure_low_kpa_g} kPa(g)",
                                direction="LOW",
                                severity=0.70,
                                confidence=0.90,
                                input_lineage=[m.signal_id],
                                reason_codes=["SEALED_TANK_DEPRESSURIZATION_OR_WEEP"],
                                hypothesis_codes=["CORRUGATED_TANK_BREACH", "SEAL_WEEP_INVENTORY_LOSS"],
                            )
                        )

    # 7. Stuck Oil Level Gauge Check (Extra A)
    if has_oil_gauge and history_buffer is not None:
        oil_meas = next((m for m in event.measurements if m.signal_id in ("oil_level", "oil_level_pct") and isinstance(m.value, (int, float)) and not isinstance(m.value, bool)), None)
        if oil_meas is not None:
            oil_val = float(oil_meas.value)
            oil_history = history_buffer.get("oil_level_pct") or history_buffer.get("oil_level") or []
            if len(oil_history) >= 3 and math.isfinite(oil_val):
                recent_levels = [x[1] for x in oil_history[-3:]] + [oil_val]
                if all(math.isfinite(lvl) for lvl in recent_levels) and len(set(recent_levels)) == 1:  # Gauge frozen completely
                    temp_meas = next((m for m in event.measurements if m.signal_id in ("top_oil_temperature", "top_oil_temp", "oti", "oil_temperature") and isinstance(m.value, (int, float)) and not isinstance(m.value, bool)), None)
                    temp_val = float(temp_meas.value) if temp_meas else None
                    temp_hist = history_buffer.get("top_oil_temperature") or history_buffer.get("top_oil_temp") or history_buffer.get("oti") or []
                    if len(temp_hist) >= 3 and temp_val is not None and math.isfinite(temp_val):
                        t_vals = [x[1] for x in temp_hist[-3:]] + [temp_val]
                        # Verify chronological monotonic ordering and reasonable step gap (max 2h per step)
                        ts_levels = [x[0] for x in oil_history[-3:]] + [event.event_time_utc]
                        is_monotonic = all(t2 > t1 for t1, t2 in zip(ts_levels[:-1], ts_levels[1:]))
                        max_gap_s = max((t2 - t1).total_seconds() for t1, t2 in zip(ts_levels[:-1], ts_levels[1:])) if is_monotonic else 999999
                        if is_monotonic and max_gap_s <= 7200 and all(math.isfinite(t) for t in t_vals):
                            if (max(t_vals) - min(t_vals)) >= 5.0:  # Temp varied while level stuck
                                evidence.append(
                                    EvidenceItem(
                                        evidence_id=f"ev_{event.asset_id}_prot_oil_stuck_{t_str}",
                                        asset_id=event.asset_id,
                                        event_time_utc=event.event_time_utc,
                                        category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                                        detector_id="DET_OIL_LEVEL_GAUGE_STUCK",
                                        observed_value=round(recent_levels[-1], 1),
                                        expected_value="LEVEL_FOLLOWS_TEMPERATURE",
                                        unit="%",
                                        threshold_or_band="FROZEN_LEVEL_WITH_DELTA_T_GE_5C",
                                        direction="FLATLINE",
                                        severity=0.60,
                                        confidence=0.90,
                                        input_lineage=["oil_level_pct", "top_oil_temperature"],
                                        reason_codes=["OIL_LEVEL_GAUGE_STUCK"],
                                        hypothesis_codes=["MECHANICAL_FLOAT_JAMMED", "LEVEL_TRANSMITTER_FAULT"],
                                    )
                                )

    # 8. Online Oil Level Trend Fallback (when precomputed trend is absent)
    has_precomputed_trend = any(m.signal_id == "oil_level_trend_pct_per_day" for m in event.measurements)
    is_stuck_gauge = any(ev.detector_id == "DET_OIL_LEVEL_GAUGE_STUCK" for ev in evidence)

    if has_oil_gauge and history_buffer is not None and not has_precomputed_trend and not is_stuck_gauge:
        oil_meas = next(
            (m for m in event.measurements if m.signal_id in ("oil_level", "oil_level_pct")
             and isinstance(m.value, (int, float)) and not isinstance(m.value, bool)),
            None
        )
        temp_meas = next(
            (m for m in event.measurements if m.signal_id in ("top_oil_temperature", "top_oil_temp", "oti", "oil_temperature")
             and isinstance(m.value, (int, float)) and not isinstance(m.value, bool)),
            None
        )
        if oil_meas is not None and temp_meas is not None:
            oil_bad = bool(oil_meas.quality and oil_meas.quality.severity == QualitySeverity.BAD)
            temp_bad = bool(temp_meas.quality and temp_meas.quality.severity == QualitySeverity.BAD)
            if not oil_bad and not temp_bad:
                oil_val = float(oil_meas.value)
                temp_val = float(temp_meas.value)
                if math.isfinite(oil_val) and math.isfinite(temp_val):
                    ref_temp = float(getattr(profile, "oil_level_ref_temp_c", 30.0) or 30.0) if profile else 30.0
                    # Documented bulk-oil temperature correction: level - 0.75 * (top_oil - ref_temp)
                    corr_level = oil_val - 0.75 * (temp_val - ref_temp)

                    buf_key = f"_online_corr_oil_{event.asset_id}"
                    c_buf = history_buffer.setdefault(buf_key, [])
                    if not c_buf or c_buf[-1][0] < event.event_time_utc:
                        c_buf.append((event.event_time_utc, corr_level))

                    # Retain last 100 entries within 72 hours
                    cutoff = event.event_time_utc - timedelta(hours=72)
                    c_buf = [(t, v) for t, v in c_buf if t >= cutoff][-100:]
                    history_buffer[buf_key] = c_buf

                    # Robust multi-day trend requires at least 6 samples spanning >= 12 hours
                    if len(c_buf) >= 6:
                        t_start, t_end = c_buf[0][0], c_buf[-1][0]
                        span_s = (t_end - t_start).total_seconds()
                        if span_s >= 43200.0:
                            t0_ref = t_start
                            t_days = [(t - t0_ref).total_seconds() / 86400.0 for t, _ in c_buf]
                            y_vals = [v for _, v in c_buf]
                            n_pts = len(y_vals)
                            st = sum(t_days)
                            sy = sum(y_vals)
                            stt = sum(t * t for t in t_days)
                            sty = sum(t * y for t, y in zip(t_days, y_vals))
                            denom = n_pts * stt - (st ** 2)
                            if denom > 1e-9:
                                slope = (n_pts * sty - st * sy) / denom
                                if slope <= thresholds.oil_leak_trend_threshold_pct_per_day:
                                    warn_th = thresholds.oil_level_warning_pct
                                    days_to_warn = max(0.0, (corr_level - warn_th) / abs(slope)) if corr_level > warn_th else 0.0
                                    span_h = span_s / 3600.0
                                    conf = min(0.90, max(0.50, 0.50 + 0.40 * (span_h / 48.0)))
                                    evidence.append(
                                        EvidenceItem(
                                            evidence_id=f"ev_{event.asset_id}_prot_oil_trend_est_{t_str}",
                                            asset_id=event.asset_id,
                                            event_time_utc=event.event_time_utc,
                                            category=AnomalyCategory.PROTECTION_OR_OIL_STATUS,
                                            detector_id="DET_OIL_LEVEL_DECLINING_TREND",
                                            observed_value=round(slope, 3),
                                            expected_value=f"> {thresholds.oil_leak_trend_threshold_pct_per_day} %/day (ESTIMATE)",
                                            unit="percent/day",
                                            threshold_or_band=f"<= {thresholds.oil_leak_trend_threshold_pct_per_day} %/day (EST_DAYS_TO_WARN={round(days_to_warn, 1)})",
                                            direction="LOW",
                                            severity=0.75,
                                            confidence=round(conf, 2),
                                            input_lineage=[oil_meas.signal_id, temp_meas.signal_id],
                                            reason_codes=["OIL_LEAK_TREND_ONLINE_ESTIMATE", "DECLINING_OIL_LEVEL_TREND"],
                                            hypothesis_codes=["EXTERNAL_TANK_OR_VALVE_LEAK", "CONSERVATOR_MEMBRANE_RUPTURE"],
                                        )
                                    )

    return evidence



# ---------------------------------------------------------------------------
# Unified Multi-Domain Anomaly Engine
# ---------------------------------------------------------------------------


class MultiDomainAnomalyEngine:
    """Unified deterministic multi-domain anomaly evaluation engine.

    Orchestrates all 8 canonical anomaly detectors across incoming telemetry events,
    accumulating stateful plausibility buffers and emitting structured EvidenceItem records.
    """

    def __init__(
        self,
        asset_id: str,
        thresholds: Optional[AnomalyDetectorThresholds] = None,
        qualification: Optional[ThermalModelQualification] = None,
        profile: Optional[AssetProfile] = None,
    ) -> None:
        """Initialize MultiDomainAnomalyEngine.

        Args:
            asset_id: Transformer asset identifier.
            thresholds: Optional custom detector thresholds.
            qualification: Optional thermal model qualification metadata.
            profile: Optional asset nameplate/profile parameters.
        """
        self.asset_id = str(asset_id)
        self.thresholds = thresholds or DEFAULT_DETECTOR_THRESHOLDS
        self.qualification = qualification
        self.profile = profile

        # Internal history buffer for sensor flatline / rate-of-change detection
        self._history_buffer: Dict[str, List[Tuple[datetime, float]]] = {}

    def evaluate_event(
        self,
        event: CanonicalEvent,
        derived: Optional[DerivedFeatures] = None,
        thermal_output: Optional[ThermalRuntimeOutput] = None,
    ) -> List[EvidenceItem]:
        """Evaluate a single CanonicalEvent against all 8 anomaly domains.

        Returns:
            List[EvidenceItem]: All structured deterministic evidence items emitted.
        """
        if event.asset_id != self.asset_id:
            raise ValueError(
                f"Asset mismatch in MultiDomainAnomalyEngine: expected '{self.asset_id}', got '{event.asset_id}'"
            )

        ev_time = event.event_time_utc
        if ev_time.tzinfo is None:
            ev_time = ev_time.replace(tzinfo=timezone.utc)

        all_evidence: List[EvidenceItem] = []

        # 1. DATA_QUALITY
        all_evidence.extend(
            detect_data_quality(event=event, derived=derived, thresholds=self.thresholds)
        )

        # 2. SENSOR_PLAUSIBILITY
        all_evidence.extend(
            detect_sensor_plausibility(
                event=event,
                history_buffer=self._history_buffer,
                thresholds=self.thresholds,
            )
        )

        # 3. THERMAL_DEVIATION
        all_evidence.extend(
            detect_thermal_deviation(
                event=event,
                thermal_output=thermal_output,
                qualification=self.qualification,
            )
        )

        # 4. THERMAL_LIMIT
        all_evidence.extend(
            detect_thermal_limits(event=event, thresholds=self.thresholds)
        )

        # 5. LOADING
        all_evidence.extend(
            detect_loading(
                event=event,
                derived=derived,
                profile=self.profile,
                thresholds=self.thresholds,
            )
        )

        # 6. PHASE_OR_NEUTRAL
        all_evidence.extend(
            detect_phase_neutral(event=event, derived=derived, thresholds=self.thresholds)
        )

        # 7. VOLTAGE_PF_FREQUENCY
        all_evidence.extend(
            detect_voltage_pf_frequency(
                event=event,
                derived=derived,
                profile=self.profile,
                thresholds=self.thresholds,
            )
        )

        # 8. PROTECTION_OR_OIL_STATUS
        all_evidence.extend(
            detect_protection_oil_status(
                event=event,
                profile=self.profile,
                history_buffer=self._history_buffer,
                thresholds=self.thresholds,
            )
        )

        # Update history buffer with current numeric readings
        for m in event.measurements:
            if isinstance(m.value, (int, float)) and not isinstance(m.value, bool):
                key = m.signal_id if m.phase is None else f"{m.signal_id}_{m.phase}"
                buf = self._history_buffer.setdefault(key, [])
                buf.append((ev_time, float(m.value)))
                # Retain last 100 readings per signal (covers 50h at 30m cadence)
                if len(buf) > 100:
                    self._history_buffer[key] = buf[-100:]

        return all_evidence

    def reset_history(self) -> None:
        """Reset internal history buffers."""
        self._history_buffer.clear()
