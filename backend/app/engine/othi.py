"""Phase 6.1 — Multi-Domain Operational Transformer Health Index (OTHI) Engine.

Implements:
1. Exact 5 canonical health domains: thermal, loading, phase_neutral, voltage_pf_freq, oil_protection.
2. Evidence-family dependency grouping and deduplication.
3. MAX_PLUS_SECONDARY_V1 aggregation algorithm with locked secondary_coefficient = 0.20.
4. Exact multi-domain evidence gating (>= 2 current domains or 1 decisive direct trip required).
5. Hybrid stale-domain tracking and Anti-Uplift Rule (loss of observability never improves health).
6. Evidence Grade (A, B, C, U) computation.
7. Raw instantaneous vs persisted operational health-band evaluation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Literal, Optional, Sequence, Set, Tuple

from app.engine.feedback import ALLOWED_P0_RESOLUTION_REASON_CODES
from app.models.anomaly import AnomalyCategory, AnomalyEpisode, EpisodeState, EvidenceItem
from app.models.features import DerivedFeatures
from app.models.health import (
    DomainFreshness,
    DomainHealth,
    EvidenceGrade,
    HealthStatus,
    OTHIBundle,
)
from app.models.telemetry import CanonicalEvent, Measurement, QualitySeverity


CANONICAL_DOMAINS: List[Literal["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"]] = [
    "thermal",
    "loading",
    "phase_neutral",
    "voltage_pf_freq",
    "oil_protection",
]

# Signals associated with each domain for freshness checking
DOMAIN_SIGNAL_MAPPING: Dict[str, Set[str]] = {
    "thermal": {
        "top_oil_temperature",
        "top_oil_temp_degc",
        "top_oil_temp",
        "ambient_temperature",
        "ambient_temp",
        "winding_temperature_indicator",
    },
    "loading": {
        "apparent_power_total",
        "active_power_total",
        "current_l1",
        "current_l2",
        "current_l3",
        "current_i1",
        "current_i2",
        "current_i3",
    },
    "phase_neutral": {
        "current_l1",
        "current_l2",
        "current_l3",
        "current_i1",
        "current_i2",
        "current_i3",
        "neutral_current",
    },
    "voltage_pf_freq": {
        "voltage_l1_n",
        "voltage_l2_n",
        "voltage_l3_n",
        "voltage_v1",
        "voltage_v2",
        "voltage_v3",
        "voltage_l1_l2",
        "voltage_l2_l3",
        "voltage_l3_l1",
        "voltage_ll_v",
        "power_factor_total",
        "frequency",
    },
    "oil_protection": {
        "top_oil_temp_trip",
        "top_oil_temp_alarm",
        "oil_temp_trip_flag",
        "oil_temp_alarm_flag",
        "oti_t",
        "oti_a",
        "oti_trip",
        "oti_alarm",
        "oti_alarm_contact",
        "oti_trip_contact",
        "breaker_trip",
        "buchholz_trip",
        "buchholz_alarm",
        "lv_breaker_closed",
        "lv_breaker_trip",
        "hv_fuse_operated",
        "magnetic_oil_gauge_alarm",
        "mog_a",
        "mog_alarm",
        "oil_level_percent",
        "oil_level_pct",
        "oil_level_status",
        "oil_level_low_alarm",
        "oil_level_corrected_pct",
        "oil_level_trend_pct_per_day",
        "oli",
        "tank_pressure_kpa_g",
        "tank_pressure",
        "pressure_kpa",
        "pressure_alarm",
        "tank_pressure_alarm",
        "prd_operated",
        "pressure_relief_operated",
        "pressure_corrected_kpa_g",
        "pressure_trend_kpa_per_day",
    },
}

# Category to domain mapping
CATEGORY_TO_DOMAIN: Dict[AnomalyCategory, Optional[str]] = {
    AnomalyCategory.THERMAL_LIMIT: "thermal",
    AnomalyCategory.THERMAL_DEVIATION: "thermal",
    AnomalyCategory.LOADING: "loading",
    AnomalyCategory.PHASE_OR_NEUTRAL: "phase_neutral",
    AnomalyCategory.VOLTAGE_PF_FREQUENCY: "voltage_pf_freq",
    AnomalyCategory.PROTECTION_OR_OIL_STATUS: "oil_protection",
    AnomalyCategory.DATA_QUALITY: None,  # Data quality affects grade, NOT physical domain severity
    AnomalyCategory.SENSOR_PLAUSIBILITY: None,  # Plausibility affects grade, NOT physical domain severity
}

# Detector to condition family mapping
DETECTOR_TO_FAMILY: Dict[str, Tuple[Optional[str], str]] = {
    # Thermal
    "DET_THERMAL_LIMIT_OTI": ("thermal", "THERMAL_LIMIT_EXCEEDANCE"),
    "DET_THERMAL_LIMIT_RISE": ("thermal", "THERMAL_LIMIT_EXCEEDANCE"),
    "DET_THERMAL_LIMIT_ABSOLUTE": ("thermal", "THERMAL_LIMIT_EXCEEDANCE"),
    "DET_THERMAL_SHADOW_DESCRIPTIVE": (None, "THERMAL_DEVIATION_UNQUALIFIED"),
    "DET_THERMAL_RESIDUAL_POINT": ("thermal", "THERMAL_DEVIATION_UNEXPECTED"),
    "DET_THERMAL_CUSUM_DRIFT": ("thermal", "THERMAL_DEVIATION_UNEXPECTED"),
    # Loading
    "DET_LOADING_OVERLOAD": ("loading", "LOADING_STRESS"),
    "DET_LOAD_RELATIVE_INDEX": ("loading", "LOADING_STRESS"),
    # Phase & Neutral
    "DET_PHASE_CURRENT_IMBALANCE": ("phase_neutral", "PHASE_CURRENT_IMBALANCE"),
    "DET_NEUTRAL_CURRENT_EXCESS": ("phase_neutral", "NEUTRAL_CURRENT_EXCESS"),
    "DET_NEUTRAL_CURRENT_RATIO": ("phase_neutral", "NEUTRAL_CURRENT_EXCESS"),
    # Voltage & PF
    "DET_VOLTAGE_IMBALANCE": ("voltage_pf_freq", "VOLTAGE_MAGNITUDE_IMBALANCE"),
    "DET_VOLTAGE_UNDERVOLTAGE": ("voltage_pf_freq", "VOLTAGE_OUT_OF_BOUNDS"),
    "DET_VOLTAGE_OVERVOLTAGE": ("voltage_pf_freq", "VOLTAGE_OUT_OF_BOUNDS"),
    "DET_VOLTAGE_SAG_OR_UNDERVOLTAGE": ("voltage_pf_freq", "VOLTAGE_OUT_OF_BOUNDS"),
    "DET_VOLTAGE_SWELL_OR_OVERVOLTAGE": ("voltage_pf_freq", "VOLTAGE_OUT_OF_BOUNDS"),
    "DET_PF_LOW": ("voltage_pf_freq", "LOW_POWER_FACTOR"),
    "DET_LOW_POWER_FACTOR": ("voltage_pf_freq", "LOW_POWER_FACTOR"),
    # Protection & Contacts
    "DET_PROT_TRIP_DISCRETE": ("oil_protection", "DIRECT_PROTECTION_TRIP"),
    "DET_PROT_ALARM_DISCRETE": ("oil_protection", "PROTECTION_ALARM"),
    "DET_PROT_WTI_CONTACT": ("oil_protection", "DIRECT_PROTECTION_TRIP"),
    "DET_PROT_OTI_TRIP": ("oil_protection", "DIRECT_PROTECTION_TRIP"),
    "DET_PROT_OTI_ALARM": ("oil_protection", "PROTECTION_ALARM"),
    "DET_PROT_LV_BREAKER_TRIP": ("oil_protection", "DIRECT_PROTECTION_TRIP"),
    "DET_PROT_HV_FUSE_OPERATED": ("oil_protection", "DIRECT_PROTECTION_TRIP"),
    # Conservator Oil Level
    "DET_PROT_MOG_ALARM": ("oil_protection", "OIL_LEVEL_ABNORMAL"),
    "DET_OIL_LEVEL_LOW": ("oil_protection", "OIL_LEVEL_ABNORMAL"),
    "DET_OIL_LEVEL_INDICATOR": ("oil_protection", "OIL_LEVEL_ABNORMAL"),
    "DET_OIL_LEVEL_DECLINING_TREND": ("oil_protection", "OIL_LEVEL_ABNORMAL"),
    "DET_OIL_LEVEL_GAUGE_STUCK": ("oil_protection", "OIL_LEVEL_ABNORMAL"),
    # Sealed-Tank Pressure
    "DET_PRESSURE_RELIEF_OPERATED": ("oil_protection", "DIRECT_PROTECTION_TRIP"),
    "DET_PRESSURE_ALARM_CONTACT": ("oil_protection", "TANK_PRESSURE_ABNORMAL"),
    "DET_PRESSURE_HIGH_ALARM": ("oil_protection", "TANK_PRESSURE_ABNORMAL"),
    "DET_PRESSURE_LOW_ALARM": ("oil_protection", "TANK_PRESSURE_ABNORMAL"),
    "DET_PRESSURE_HIGH_TRANSIENT": ("oil_protection", "TANK_PRESSURE_TRANSIENT"),
    "DET_PRESSURE_LOW_TRANSIENT": ("oil_protection", "TANK_PRESSURE_TRANSIENT"),
    # Electrical Episode Engine mappings
    "EPISODE_CURRENT_IMBALANCE": ("phase_neutral", "PHASE_CURRENT_IMBALANCE"),
    "EPISODE_VOLTAGE_IMBALANCE": ("voltage_pf_freq", "VOLTAGE_MAGNITUDE_IMBALANCE"),
    "EPISODE_NEUTRAL_CURRENT_RATIO": ("phase_neutral", "NEUTRAL_CURRENT_EXCESS"),
    "EPISODE_LOW_POWER_FACTOR": ("voltage_pf_freq", "LOW_POWER_FACTOR"),
    "EPISODE_PQS_INCONSISTENCY": (None, "DATA_QUALITY_ANOMALY"),
}


# Detectors whose evidence is shadow / descriptive only and never penalizes OTHI:
# - thermal CUSUM runs on an autocorrelated free-running residual (lag-1 ~0.95), violating its iid
#   assumption, so it alarms on most normal frames;
# - the oil-leak trend uses short-window slopes with an uncalibrated threshold that the normal
#   thermal-expansion cycle crosses on about half of all frames.
# They stay visible as evidence and advisories until requalified.
SHADOW_ONLY_DETECTORS: frozenset[str] = frozenset({
    "DET_THERMAL_CUSUM_DRIFT",
    "DET_THERMAL_SHADOW_DESCRIPTIVE",
    "DET_OIL_LEVEL_DECLINING_TREND",
})

# Protection advisory identity (rules.yaml MNT-PROT-001) used to scope authorized trip resolutions
PROTECTION_TRIP_RULE_ID = "MNT-PROT-001"
PROTECTION_TRIP_MERGE_KEYS: frozenset[str] = frozenset({"SAFETY_PROTECTION_TRIP", "PROTECTION_TRIP_FOLLOWUP"})


def is_authorized_trip_resolution(
    action: Any,
    reason_code: Optional[str],
    recommendation_id: Optional[str] = None,
    merge_key: Optional[str] = None,
) -> bool:
    """Whether a feedback action is an authorized resolution of a latched protection trip.

    Only a RESOLVE/DISMISS that targets the protection advisory (MNT-PROT-001) with a documented
    P0 resolution reason code qualifies. ACKNOWLEDGE never qualifies, and resolving an unrelated
    advisory never clears a genuine trip, whatever its reason code.
    """
    action_val = str(action.value if hasattr(action, "value") else action or "").upper()
    if action_val not in ("RESOLVE", "DISMISS"):
        return False
    if reason_code not in ALLOWED_P0_RESOLUTION_REASON_CODES:
        return False
    targets_protection = PROTECTION_TRIP_RULE_ID in (recommendation_id or "").upper()
    return targets_protection or (merge_key or "").upper() in PROTECTION_TRIP_MERGE_KEYS


def status_from_severity(severity: float) -> HealthStatus:
    """Map normalized domain penalty severity in [0.0, 1.0] to health status."""
    if severity >= 0.61:
        return HealthStatus.CRITICAL
    elif severity >= 0.41:
        return HealthStatus.WARNING
    elif severity >= 0.21:
        return HealthStatus.WATCH
    return HealthStatus.NORMAL


def status_from_othi(score: int | None) -> HealthStatus | None:
    """Map integer OTHI score in [0, 100] to operational health status."""
    if score is None:
        return None
    if score >= 80:
        return HealthStatus.NORMAL
    elif score >= 60:
        return HealthStatus.WATCH
    elif score >= 40:
        return HealthStatus.WARNING
    else:
        return HealthStatus.CRITICAL


def aggregate_othi_max_plus_secondary(
    domain_severities: Dict[str, float],
    secondary_coefficient: float = 0.20,
) -> Tuple[int, float, float, float, Optional[str]]:
    """Execute locked MAX_PLUS_SECONDARY_V1 aggregation algorithm.

    Formula:
        base_penalty = max(s_d)
        secondary_penalty = 0.20 * sum_{d != base}(s_d)
        total_penalty = min(1.0, base_penalty + secondary_penalty)
        OTHI = round(100 * (1 - total_penalty))

    Args:
        domain_severities: Dict of available domain severities in [0.0, 1.0].
        secondary_coefficient: Product policy secondary coefficient (default 0.20).

    Returns:
        Tuple of (othi_score, base_penalty, secondary_penalty, total_penalty, driving_domain).
    """
    if not domain_severities:
        return 100, 0.0, 0.0, 0.0, None

    # Deterministic tie-breaking for driving domain: highest severity, then alphabetical domain name
    sorted_domains = sorted(
        domain_severities.items(),
        key=lambda item: (-item[1], item[0]),
    )
    driving_domain, base_penalty = sorted_domains[0]

    # Secondary penalty from other available domains
    secondary_sum = sum(s for d, s in sorted_domains[1:])
    secondary_penalty = secondary_coefficient * secondary_sum
    total_penalty = min(1.0, base_penalty + secondary_penalty)
    raw_score = round(100.0 * (1.0 - total_penalty))
    clamped_score = max(0, min(100, raw_score))

    return clamped_score, base_penalty, secondary_penalty, total_penalty, driving_domain


def aggregate_othi_v2(
    domain_severities: Dict[str, float],
    secondary_coefficient: float = 0.25,
) -> Tuple[int, float, float, float, Optional[str]]:
    """Execute literature-grounded OTHI_V2 aggregation algorithm (CIGRE TB 761, Li et al. 2023).

    Formula:
        base_penalty = max(s_d)
        probabilistic_secondary = 1.0 - prod_{d != base}(1.0 - s_d)
        secondary_penalty = secondary_coefficient * (1.0 - base_penalty) * probabilistic_secondary
        total_penalty = base_penalty + secondary_penalty
        OTHI = round(100 * (1 - total_penalty))

    Guarantees:
        1. Monotonicity: Increasing any domain severity cannot improve the score.
        2. Strict bounding: Total penalty is intrinsically bounded in [0.0, 1.0].
        3. Worst-domain dominance: If base_penalty == 1.0, total_penalty == 1.0 and OTHI == 0.
        4. Diminishing returns: Multiple mild anomalies compound without linear cliff over-penalization.
        5. Deterministic tie-breaking: Alphabetical domain name.

    Args:
        domain_severities: Dict of available domain severities in [0.0, 1.0].
        secondary_coefficient: Compounding factor gamma (default 0.25).

    Returns:
        Tuple of (othi_score, base_penalty, secondary_penalty, total_penalty, driving_domain).
    """
    if not domain_severities:
        return 100, 0.0, 0.0, 0.0, None

    sorted_domains = sorted(
        domain_severities.items(),
        key=lambda item: (-item[1], item[0]),
    )
    driving_domain, base_penalty = sorted_domains[0]

    # Probabilistic product accumulation for secondary domains
    prod_complement = 1.0
    for _, s in sorted_domains[1:]:
        s_clamped = max(0.0, min(1.0, float(s)))
        prod_complement *= (1.0 - s_clamped)

    probabilistic_secondary = 1.0 - prod_complement
    secondary_penalty = float(secondary_coefficient) * (1.0 - base_penalty) * probabilistic_secondary
    total_penalty = min(1.0, max(0.0, base_penalty + secondary_penalty))

    raw_score = round(100.0 * (1.0 - total_penalty))
    clamped_score = max(0, min(100, raw_score))

    return clamped_score, base_penalty, secondary_penalty, total_penalty, driving_domain


class OTHIEngine:
    """Stateful Multi-Domain OTHI Aggregator and Health Assessment Engine."""

    def __init__(
        self,
        expected_cadence_seconds: float = 900.0,  # 15 min default
        secondary_coefficient: Optional[float] = None,
        algorithm_version: str = "MAX_PLUS_SECONDARY_V1",
    ) -> None:
        """Initialize OTHIEngine.

        Args:
            expected_cadence_seconds: Expected asset sampling interval in seconds.
            secondary_coefficient: Product policy secondary penalty factor.
            algorithm_version: Aggregation algorithm ('MAX_PLUS_SECONDARY_V1' or 'OTHI_V2').
        """
        self.expected_cadence_seconds = expected_cadence_seconds
        self.algorithm_version = algorithm_version
        if secondary_coefficient is None:
            self.secondary_coefficient = 0.25 if algorithm_version == "OTHI_V2" else 0.20
        else:
            self.secondary_coefficient = secondary_coefficient
        self.warning_stale_seconds = max(2.0 * expected_cadence_seconds, 600.0)  # max(2*cadence, 10 min)
        self.hard_stale_seconds = max(4.0 * expected_cadence_seconds, 3600.0)    # max(4*cadence, 60 min)

        # Stateful memory for last valid observations and uncleared degraded state
        self.last_valid_time_by_domain: Dict[str, datetime] = {}
        self.last_valid_severity_by_domain: Dict[str, float] = {}
        self.latched_protection_trip: bool = False
        self.latched_trip_time_utc: Optional[datetime] = None
        # Ledger length when the trip latched: only resolutions appended after it may unlatch
        self.latched_ledger_index: Optional[int] = None
        self.last_valid_othi_score: Optional[int] = None
        self.last_valid_status: Optional[HealthStatus] = None
        self.last_valid_timestamp_utc: Optional[datetime] = None
        self.feedback_ledger: Optional[Any] = None
        self.current_asset_id: Optional[str] = None
        self.persistence_seconds: float = max(expected_cadence_seconds, 600.0)
        self.degradation_candidate_start_time: Optional[datetime] = None
        self.degradation_candidate_score: Optional[int] = None

    def reset_protection_trip(self) -> None:
        """Unlatch direct protection trip after authorized resolution."""
        self.latched_protection_trip = False
        self.latched_trip_time_utc = None
        self.latched_ledger_index = None
        self.last_valid_severity_by_domain.pop("oil_protection", None)
        self.last_valid_time_by_domain.pop("oil_protection", None)
        self.last_valid_othi_score = None
        self.last_valid_status = None
        self.degradation_candidate_start_time = None
        self.degradation_candidate_score = None

    def reset(self) -> None:
        """Reset internal stateful memory and trip latch."""
        self.last_valid_time_by_domain.clear()
        self.last_valid_severity_by_domain.clear()
        self.latched_protection_trip = False
        self.latched_trip_time_utc = None
        self.latched_ledger_index = None
        self.last_valid_othi_score = None
        self.last_valid_status = None
        self.last_valid_timestamp_utc = None
        self.current_asset_id = None
        self.degradation_candidate_start_time = None
        self.degradation_candidate_score = None

    def _aggregate(
        self,
        domain_severities: Dict[str, float],
    ) -> Tuple[int, float, float, float, Optional[str]]:
        """Run configured aggregation algorithm."""
        if self.algorithm_version == "OTHI_V2":
            return aggregate_othi_v2(
                domain_severities=domain_severities,
                secondary_coefficient=self.secondary_coefficient,
            )
        return aggregate_othi_max_plus_secondary(
            domain_severities=domain_severities,
            secondary_coefficient=self.secondary_coefficient,
        )

    def _resolve_evidence_family(self, ev: EvidenceItem) -> Tuple[Optional[str], str]:
        """Determine domain and condition_family for an EvidenceItem."""
        if ev.domain and ev.condition_family:
            return ev.domain, ev.condition_family

        if ev.detector_id in DETECTOR_TO_FAMILY:
            domain, family = DETECTOR_TO_FAMILY[ev.detector_id]
            return (None if domain == "DATA_QUALITY" else domain), family

        # Fallback via AnomalyCategory
        domain = CATEGORY_TO_DOMAIN.get(ev.category)
        family = ev.category.value
        return domain, family

    def _evaluate_domain_freshness(
        self,
        domain: str,
        current_time: datetime,
        present_signals: Set[str],
    ) -> Tuple[DomainFreshness, Optional[datetime]]:
        """Determine freshness state of a domain based on current and historical telemetry."""
        domain_signals = DOMAIN_SIGNAL_MAPPING.get(domain, set())
        has_current_signals = bool(domain_signals.intersection(present_signals))

        # Direct protection trip makes oil_protection domain active, current, and decisive
        if domain == "oil_protection" and self.latched_protection_trip:
            self.last_valid_time_by_domain[domain] = current_time
            return DomainFreshness.CURRENT, current_time

        if has_current_signals:
            self.last_valid_time_by_domain[domain] = current_time
            return DomainFreshness.CURRENT, current_time

        last_seen = self.last_valid_time_by_domain.get(domain)
        if last_seen is None:
            return DomainFreshness.UNAVAILABLE, None

        age_seconds = (current_time - last_seen).total_seconds()
        if age_seconds <= self.warning_stale_seconds:
            return DomainFreshness.CURRENT, last_seen
        elif age_seconds <= self.hard_stale_seconds:
            return DomainFreshness.WARNING_STALE, last_seen
        else:
            return DomainFreshness.HARD_STALE, last_seen

    def evaluate(
        self,
        event: CanonicalEvent,
        derived: Optional[DerivedFeatures] = None,
        evidence_items: Optional[Sequence[EvidenceItem]] = None,
        open_episodes: Optional[Sequence[AnomalyEpisode]] = None,
        previous_bundle: Optional[OTHIBundle] = None,
        feedback_ledger: Optional[Any] = None,
    ) -> OTHIBundle:
        """Evaluate multi-domain severities, evidence gating, anti-uplift, and OTHI score.

        Args:
            event: Current incoming CanonicalEvent.
            derived: Optional derived electrical features.
            evidence_items: Current active EvidenceItem records emitted by detectors.
            open_episodes: Current active and recovering AnomalyEpisode incidents.
            previous_bundle: Previous OTHIBundle for continuity and anti-uplift checks.
            feedback_ledger: Optional OperatorFeedbackLedger instance.

        Returns:
            OTHIBundle: Immutable complete condition assessment.
        """
        current_time = event.event_time_utc
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Asset boundary isolation: reset stateful tracking if asset changes
        if self.current_asset_id is not None and self.current_asset_id != event.asset_id:
            self.reset()
        self.current_asset_id = event.asset_id

        # 1. Identify present good/usable signals in this event
        present_signals: Set[str] = set()
        for m in event.measurements:
            is_direct_trip = "DIRECT_TRIP" in (m.quality.flags if m.quality else [])
            if m.quality.severity != QualitySeverity.BAD or is_direct_trip:
                present_signals.add(m.signal_id)

        # 2. Check for latched protection trip and lifecycle
        current_trip_active = False
        trip_signals_present = False
        for m in event.measurements:
            s_id = m.signal_id.lower()
            flags = m.quality.flags if m.quality else []
            # A contact read from a bad-quality frame (e.g. comm loss) is not trip evidence,
            # unless the source explicitly marks it as a direct trip
            if m.quality and m.quality.severity == QualitySeverity.BAD and "DIRECT_TRIP" not in flags:
                continue
            if s_id in (
                "top_oil_temp_trip",
                "breaker_trip",
                "oil_temp_trip_flag",
                "oti_t",
                "oti_trip",
                "oti_trip_contact",
                "buchholz_trip",
                "lv_breaker_trip",
                "hv_fuse_operated",
                "prd_operated",
                "pressure_relief_operated",
            ) or "DIRECT_TRIP" in flags:
                trip_signals_present = True
                val = m.value
                if val is True or val == 1 or str(val).lower() in ("true", "1", "trip", "tripped"):
                    current_trip_active = True
                    self.latched_protection_trip = True
            elif s_id in ("lv_breaker_closed", "52a_status"):
                val = m.value
                if val in (0, 0.0, "0", False, "false", "open", "OPEN"):
                    trip_signals_present = True
                    current_trip_active = True
                    self.latched_protection_trip = True

        if "PROTECTION_TRIP_ACTIVE" in (event.event_quality_flags or []):
            current_trip_active = True
            self.latched_protection_trip = True

        if evidence_items:
            for ev in evidence_items:
                if (
                    ev.condition_family == "DIRECT_PROTECTION_TRIP"
                    or ev.detector_id in ("DET_PROT_LV_BREAKER_TRIP", "DET_PROT_TRIP_DISCRETE", "DET_PROT_OTI_TRIP")
                ) and ev.severity >= 0.8:
                    current_trip_active = True
                    self.latched_protection_trip = True

        ledger = feedback_ledger or self.feedback_ledger
        if current_trip_active:
            if self.latched_trip_time_utc is None:
                self.latched_trip_time_utc = current_time
                if ledger is not None:
                    self.latched_ledger_index = len(ledger.get_history(asset_id=event.asset_id))

        # Unlatch condition:
        # Trip was previously latched, current frame explicitly does NOT have an active trip,
        # AND an authorized resolution of the protection advisory was recorded after the trip latched.
        # "After" is ledger order, not timestamp: feedback is stamped with the twin watermark, which
        # trails the trip frame's event time, so a timestamp comparison can reject a genuine resolution.
        if self.latched_protection_trip and not current_trip_active and ledger is not None:
            history = ledger.get_history(asset_id=event.asset_id)
            start = self.latched_ledger_index or 0
            has_authorized_resolution = any(
                is_authorized_trip_resolution(
                    action=r.action,
                    reason_code=r.reason_code,
                    recommendation_id=r.recommendation_id,
                    merge_key=r.merge_key,
                )
                for r in history[start:]
            )
            if has_authorized_resolution:
                self.reset_protection_trip()

        # 3. Group active evidence by domain and condition family
        evidence_list = list(evidence_items or [])
        domain_family_evidence: Dict[str, Dict[str, List[EvidenceItem]]] = {
            d: {} for d in CANONICAL_DOMAINS
        }

        has_data_quality_issue = False
        for ev in evidence_list:
            if ev.category in (AnomalyCategory.DATA_QUALITY, AnomalyCategory.SENSOR_PLAUSIBILITY):
                has_data_quality_issue = True
                continue
            if ev.detector_id in SHADOW_ONLY_DETECTORS:
                continue

            domain, family = self._resolve_evidence_family(ev)
            if domain and domain in domain_family_evidence:
                if family not in domain_family_evidence[domain]:
                    domain_family_evidence[domain][family] = []
                domain_family_evidence[domain][family].append(ev)

        # 4. Evaluate Domain Health for each canonical domain
        domains_health: Dict[str, DomainHealth] = {}
        available_domains: List[str] = []
        current_domains: List[str] = []
        stale_domains: List[str] = []
        active_domain_severities: Dict[str, float] = {}
        driving_family_by_domain: Dict[str, Optional[str]] = {}

        for domain in CANONICAL_DOMAINS:
            freshness, last_seen_time = self._evaluate_domain_freshness(
                domain=domain,
                current_time=current_time,
                present_signals=present_signals,
            )

            # Check if domain has any usable telemetry or history
            is_available = freshness in (DomainFreshness.CURRENT, DomainFreshness.WARNING_STALE)
            if is_available:
                available_domains.append(domain)

            if freshness == DomainFreshness.CURRENT:
                current_domains.append(domain)
            elif freshness == DomainFreshness.WARNING_STALE:
                stale_domains.append(domain)

            # Deduplicate within domain across condition families:
            # Domain severity = max_{family}( max_{ev in family}(ev.severity) )
            family_dict = domain_family_evidence[domain]
            contributing_families = sorted(family_dict.keys())
            max_family_severity = 0.0
            driving_ev_id: Optional[str] = None
            driving_fam: Optional[str] = None
            total_ev_count = 0

            for fam, evs in family_dict.items():
                total_ev_count += len(evs)
                for ev in evs:
                    if ev.severity > max_family_severity:
                        max_family_severity = ev.severity
                        driving_ev_id = ev.evidence_id
                        driving_fam = fam

            # Direct protection trip override
            if domain == "oil_protection" and self.latched_protection_trip:
                max_family_severity = 1.0
                driving_fam = "DIRECT_PROTECTION_TRIP"
                if "DIRECT_PROTECTION_TRIP" not in contributing_families:
                    contributing_families.append("DIRECT_PROTECTION_TRIP")

            # Store last known valid severity for anti-uplift checking
            if freshness == DomainFreshness.CURRENT:
                self.last_valid_severity_by_domain[domain] = max_family_severity
                active_domain_severities[domain] = max_family_severity
                driving_family_by_domain[domain] = driving_fam
            elif freshness == DomainFreshness.WARNING_STALE:
                # Retain last severity under HELD_STALE
                held_sev = self.last_valid_severity_by_domain.get(domain, max_family_severity)
                active_domain_severities[domain] = held_sev
                driving_family_by_domain[domain] = driving_fam
            else:
                # HARD_STALE or UNAVAILABLE: not in active calculation
                pass

            dom_status = status_from_severity(max_family_severity)
            detail_msg = (
                f"{domain} condition: severity {max_family_severity:.2f} "
                f"({dom_status.value}), families: {contributing_families or ['NORMAL']}"
            )
            if freshness == DomainFreshness.WARNING_STALE:
                detail_msg += f" [HELD_STALE, last seen {last_seen_time}]"
            elif freshness == DomainFreshness.HARD_STALE:
                detail_msg += f" [HARD_STALE, dropped from calculation]"

            domains_health[domain] = DomainHealth(
                domain_name=domain,  # type: ignore[arg-type]
                severity=max_family_severity,
                status=dom_status,
                driving_evidence_id=driving_ev_id,
                driving_condition_family=driving_fam,
                evidence_count=total_ev_count,
                details=detail_msg,
                freshness=freshness,
                last_valid_time_utc=last_seen_time,
                is_stale=(freshness in (DomainFreshness.WARNING_STALE, DomainFreshness.HARD_STALE)),
                contributing_families=contributing_families,
            )

        # 5. Compute Evidence Grade
        evidence_grade = self._compute_evidence_grade(
            current_domains=current_domains,
            stale_domains=stale_domains,
            has_data_quality_issue=has_data_quality_issue,
        )

        # 6. Aggregation Algorithm & Gating
        is_direct_trip_decisive = (
            "oil_protection" in available_domains
            and active_domain_severities.get("oil_protection", 0.0) >= 1.0
        )

        has_sufficient_current_evidence = len(current_domains) >= 2 or is_direct_trip_decisive

        # Calculate raw score from current active domains
        raw_score, base_pen, sec_pen, tot_pen, driv_domain = self._aggregate(
            domain_severities={d: active_domain_severities[d] for d in current_domains},
        )
        driv_fam = driving_family_by_domain.get(driv_domain) if driv_domain else None
        raw_status = status_from_othi(raw_score)

        # 7. Apply Anti-Uplift Rule
        # If any domain is stale/missing, compute counterfactual score including the last known degraded state
        counterfactual_severities = dict(active_domain_severities)
        for d, last_sev in self.last_valid_severity_by_domain.items():
            if d not in counterfactual_severities:
                counterfactual_severities[d] = last_sev

        cf_score, _, _, _, _ = self._aggregate(
            domain_severities=counterfactual_severities,
        )

        # Anti-uplift violation: current raw score is healthier than counterfactual due to dropped stale domains
        has_anti_uplift_violation = False
        if len(stale_domains) > 0 or len(current_domains) < len(self.last_valid_severity_by_domain):
            if cf_score < raw_score:
                has_anti_uplift_violation = True

        # Determine if numeric OTHI is emitted or gated
        is_gated: bool
        gate_reason: Optional[str] = None
        final_othi: Optional[int] = None
        final_status: Optional[HealthStatus] = None

        if is_direct_trip_decisive:
            # Direct protection trip has unconditional precedence
            is_gated = False
            final_othi = 0
            final_status = HealthStatus.CRITICAL
            driv_domain = "oil_protection"
            driv_fam = "DIRECT_PROTECTION_TRIP"
            base_pen = 1.0
            tot_pen = 1.0
        elif not has_sufficient_current_evidence:
            is_gated = True
            gate_reason = "Insufficient current evidence"
            final_othi = None
            final_status = None
        elif has_anti_uplift_violation:
            is_gated = True
            gate_reason = "Insufficient fresh evidence; last known condition was degraded"
            final_othi = None
            final_status = None
        else:
            is_gated = False
            gate_reason = None

            # Distinguish slower-moving condition score from instantaneous operating stress:
            baseline_score = self.last_valid_othi_score
            has_active_degraded_episode = False
            if open_episodes:
                has_active_degraded_episode = any(
                    ep.state in (EpisodeState.CRITICAL, EpisodeState.WARNING)
                    for ep in open_episodes
                )

            if baseline_score is None:
                # Cold-start initialization without prior baseline
                final_othi = raw_score
                final_status = raw_status
                self.degradation_candidate_start_time = None
                self.degradation_candidate_score = None
            elif raw_score < baseline_score:
                # Operating stress / degradation below existing condition baseline
                if has_active_degraded_episode:
                    # Confirmed sustained by active episode engine
                    final_othi = raw_score
                    final_status = raw_status
                    self.degradation_candidate_start_time = None
                    self.degradation_candidate_score = None
                else:
                    # Evaluate temporal persistence across event time
                    if self.degradation_candidate_start_time is None:
                        self.degradation_candidate_start_time = current_time
                        self.degradation_candidate_score = raw_score

                    elapsed = (current_time - self.degradation_candidate_start_time).total_seconds()
                    if elapsed >= self.persistence_seconds:
                        # Degradation sustained across persistence window
                        final_othi = raw_score
                        final_status = raw_status
                    else:
                        # Transient operating stress / isolated 1-frame excursion:
                        # Preserve condition health score while exposing instantaneous stress in raw_othi
                        final_othi = baseline_score
                        final_status = self.last_valid_status or raw_status
            else:
                # raw_score >= baseline_score (healthy or recovering)
                self.degradation_candidate_start_time = None
                self.degradation_candidate_score = None
                if has_active_degraded_episode:
                    # Cannot recover condition score while active degraded episode remains open
                    final_othi = baseline_score
                    final_status = self.last_valid_status or raw_status
                else:
                    final_othi = raw_score
                    final_status = raw_status

        # 8. Operational Status Band via Episode Persistence & Anti-Uplift
        operational_status = self._evaluate_operational_status(
            final_status=final_status or raw_status,
            is_direct_trip=is_direct_trip_decisive,
            open_episodes=open_episodes,
        )
        if has_anti_uplift_violation and self.last_valid_status in (HealthStatus.WARNING, HealthStatus.CRITICAL):
            operational_status = self.last_valid_status

        # 9. Update last valid OTHI tracking

        if final_othi is not None:
            self.last_valid_othi_score = final_othi
            self.last_valid_status = final_status
            self.last_valid_timestamp_utc = current_time

        return OTHIBundle(
            asset_id=event.asset_id,
            timestamp_utc=current_time,
            othi_score=final_othi,
            raw_othi=raw_score if has_sufficient_current_evidence else None,
            status=final_status,
            raw_status=raw_status,
            operational_status=operational_status,
            evidence_grade=evidence_grade,
            driving_domain=driv_domain,
            driving_condition_family=driv_fam,
            base_penalty=base_pen,
            secondary_penalty=sec_pen,
            total_penalty=tot_pen,
            is_gated=is_gated,
            gate_reason=gate_reason,
            available_domains=available_domains or ["unobserved"],
            current_domains=current_domains,
            stale_domains=stale_domains,
            domains=domains_health,
            last_valid_othi=self.last_valid_othi_score,
            last_valid_status=self.last_valid_status,
            last_valid_timestamp_utc=self.last_valid_timestamp_utc,
            algorithm_version=self.algorithm_version,
            secondary_coefficient=self.secondary_coefficient,
        )

    def _compute_evidence_grade(
        self,
        current_domains: List[str],
        stale_domains: List[str],
        has_data_quality_issue: bool,
    ) -> EvidenceGrade:
        """Compute deterministic evidence grade (A, B, C, U)."""
        num_current = len(current_domains)

        if num_current == 0:
            return EvidenceGrade.U
        elif num_current >= 4 and not has_data_quality_issue and len(stale_domains) == 0:
            return EvidenceGrade.A
        elif num_current >= 2 and not has_data_quality_issue and len(stale_domains) == 0:
            return EvidenceGrade.B
        else:
            return EvidenceGrade.C

    def _evaluate_operational_status(
        self,
        final_status: Optional[HealthStatus],
        is_direct_trip: bool,
        open_episodes: Optional[Sequence[AnomalyEpisode]],
    ) -> Optional[HealthStatus]:
        """Determine operational health band respecting episode persistence."""
        if is_direct_trip:
            return HealthStatus.CRITICAL

        if final_status is None:
            return None

        # If any open episode is in CRITICAL state, operational band is CRITICAL
        if open_episodes:
            states = [ep.state for ep in open_episodes]
            if EpisodeState.CRITICAL in states:
                return HealthStatus.CRITICAL
            elif EpisodeState.WARNING in states and final_status in (HealthStatus.NORMAL, HealthStatus.WATCH):
                return HealthStatus.WARNING
            elif EpisodeState.WATCH in states and final_status == HealthStatus.NORMAL:
                return HealthStatus.WATCH

        return final_status
