"""Phase 6.3 — Deterministic Maintenance Policy & Rules Engine.

Implements:
1. Versioned rule evaluation (MNT-PROT-001 through MNT-MODEL-007) from rules.yaml.
2. Exact priority hierarchy: P0 (SAFETY) > P1 (URGENT) > P2 (PLANNED) > P3 (MONITOR) > P4 (DATA/MODEL).
3. Action window provenance tracking (PROTECTION_OR_SITE_PROCEDURE, OPERATOR_POLICY, ENGINEERING_POLICY, etc.).
4. Qualification gating: CUSUM / thermal model recommendations suppressed when unqualified (Tripura default).
5. Sensor-level bad-data suppression (suppresses dependent model rules, NEVER suppresses P0 protection).
6. Compatible recommendation merging under merge_key (retaining strictest urgency and all supporting rule IDs).
7. Incompatible recommendation escalation notice generation.
8. Advisory-only semantics with explicit preservation of project exclusions (no autonomous control, no whole-life RUL/PoF).
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set
import uuid
import yaml

from app.engine.anomaly_detectors import is_watch_level_evidence
from app.engine.feedback import OperatorFeedbackLedger, ALLOWED_P0_RESOLUTION_REASON_CODES
from app.engine.othi import SHADOW_ONLY_DETECTORS
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.health import OTHIBundle
from app.models.maintenance import (
    ActionWindow,
    ActionWindowProvenanceType,
    FeedbackAction,
    MaintenancePriority,
    MaintenanceRecommendation,
    OperatorFeedbackEvent,
)
from app.models.scenario import ScenarioProjectionResult
from app.models.telemetry import CanonicalEvent, MeasurementQuality, QualitySeverity


# Priority strictness order (lower number = higher priority)
PRIORITY_ORDER: Dict[MaintenancePriority, int] = {
    MaintenancePriority.P0_SAFETY: 0,
    MaintenancePriority.P1_URGENT_INSPECTION: 1,
    MaintenancePriority.P2_PLANNED_ACTION: 2,
    MaintenancePriority.P3_MONITOR: 3,
    MaintenancePriority.P4_DATA_OR_MODEL: 4,
}

# Action window strictness order (lower number = stricter urgency)
WINDOW_ORDER: Dict[ActionWindow, int] = {
    ActionWindow.IMMEDIATE: 0,
    ActionWindow.WITHIN_24H: 1,
    ActionWindow.NEXT_AUTHORIZED_MAINTENANCE_WINDOW: 2,
    ActionWindow.MONITOR: 3,
    ActionWindow.MODEL_REVIEW: 4,
}


class MaintenanceEngine:
    """Deterministic, rule-based maintenance policy and advisory recommendation engine."""

    def __init__(
        self,
        rules_path: Optional[str | Path] = None,
        cusum_qualification: str = "DISABLED",  # Locked qualification default for Tripura
        is_thermal_qualified: bool = False,
        is_model_promoted: bool = False,
        feedback_ledger: Optional[OperatorFeedbackLedger] = None,
    ) -> None:
        """Initialize MaintenanceEngine.

        Args:
            rules_path: Path to rules.yaml specification file.
            cusum_qualification: Qualification status of CUSUM tracker ("ENABLED" or "DISABLED").
            is_thermal_qualified: Whether thermal model is promoted for causal diagnosis.
            is_model_promoted: Whether grey-box ODE is promoted for predictive projection.
            feedback_ledger: Append-only ledger for operator feedback events.
        """
        self.cusum_qualification = cusum_qualification
        self.is_thermal_qualified = is_thermal_qualified
        self.is_model_promoted = is_model_promoted
        self.feedback_ledger = feedback_ledger or OperatorFeedbackLedger()

        # Load rules specification
        if rules_path is None:
            rules_path = Path(__file__).parent / "rules.yaml"
        self.rules_path = Path(rules_path)
        self.rules: Dict[str, Dict[str, Any]] = self._load_rules(self.rules_path)

    def reset(self) -> None:
        """Reset internal maintenance engine state."""
        pass

    def _load_rules(self, path: Path) -> Dict[str, Dict[str, Any]]:
        """Load and validate rules from YAML file."""
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rules_list = data.get("rules", [])
        return {r["rule_id"]: r for r in rules_list if "rule_id" in r}

    def record_feedback(
        self,
        feedback: OperatorFeedbackEvent,
        target_recommendation: Optional[MaintenanceRecommendation] = None,
    ) -> OperatorFeedbackEvent:
        """Record and validate an operator feedback event into the immutable ledger."""
        return self.feedback_ledger.append(feedback, target_recommendation=target_recommendation)

    def process_feedback(self, feedback: OperatorFeedbackEvent) -> None:
        """Process operator feedback (convenience method delegating to record_feedback)."""
        self.record_feedback(feedback)


    def evaluate(
        self,
        event: CanonicalEvent,
        evidence_items: Optional[Sequence[EvidenceItem]] = None,
        health_bundle: Optional[OTHIBundle] = None,
        scenario_projection: Optional[ScenarioProjectionResult] = None,
        previous_recommendations: Optional[Sequence[MaintenanceRecommendation]] = None,
    ) -> List[MaintenanceRecommendation]:
        """Evaluate active telemetry, evidence, and projections against maintenance rules.

        Args:
            event: Current incoming CanonicalEvent.
            evidence_items: Active evidence items emitted by detectors.
            health_bundle: Current OTHI health assessment.
            scenario_projection: Optional 2-hour scenario projection result.

        Returns:
            List[MaintenanceRecommendation]: Prioritized, deduplicated advisory recommendations.
        """
        current_time = event.event_time_utc
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Watch-level evidence scores OTHI only; it is not an alarm and raises no advisory
        evidence_list = [ev for ev in (evidence_items or []) if not is_watch_level_evidence(ev)]

        # 1. Identify bad quality signals to apply selective suppression
        bad_signals: Set[str] = set()
        for m in event.measurements:
            if m.quality.severity == QualitySeverity.BAD:
                bad_signals.add(m.signal_id)

        # 2. Check for direct hardware protection trip
        has_direct_trip = False
        direct_trip_evidence_ids: List[str] = []
        for m in event.measurements:
            if m.signal_id.lower() in ("top_oil_temp_trip", "breaker_trip", "buchholz_trip", "oil_temp_trip_flag", "oti_t", "wti"):
                val = m.value
                if val is True or val == 1 or str(val).lower() in ("true", "1", "trip", "tripped"):
                    has_direct_trip = True
                    break

        if "PROTECTION_TRIP_ACTIVE" in event.event_quality_flags:
            has_direct_trip = True

        for ev in evidence_list:
            if ev.condition_family in ("DIRECT_PROTECTION_TRIP", "TRIP_DISCRETE") or (
                ev.category == AnomalyCategory.PROTECTION_OR_OIL_STATUS and ev.severity >= 1.0
            ):
                has_direct_trip = True
                direct_trip_evidence_ids.append(ev.evidence_id)

        # Include latched protection trip from OTHI health assessment
        if health_bundle is not None:
            oil_prot = health_bundle.domains.get("oil_protection")
            if health_bundle.driving_condition_family == "DIRECT_PROTECTION_TRIP" or (
                oil_prot is not None and oil_prot.severity >= 1.0
            ):
                has_direct_trip = True

        fired_recommendations: List[MaintenanceRecommendation] = []

        # --- Rule 1: MNT-PROT-001 (P0 SAFETY / IMMEDIATE) ---
        if has_direct_trip and "MNT-PROT-001" in self.rules:
            r_cfg = self.rules["MNT-PROT-001"]
            rec_id = f"REC-{event.asset_id}-MNT-PROT-001"
            fired_recommendations.append(
                MaintenanceRecommendation(
                    recommendation_id=rec_id,
                    rule_id="MNT-PROT-001",
                    rule_version=r_cfg.get("version", "1.0.0"),
                    title=r_cfg.get("title", "Protection Contact Trip Action"),
                    priority=MaintenancePriority.P0_SAFETY,
                    priority_label="P0 SAFETY",
                    action_window=ActionWindow.IMMEDIATE,
                    window_provenance_type=ActionWindowProvenanceType.PROTECTION_OR_SITE_PROCEDURE,
                    window_source_reference=r_cfg.get("window_source_reference", "Utility Substation Safety Standard"),
                    advisory_wording=r_cfg.get("advisory_wording", "Follow site-approved trip and isolation procedure."),
                    rationale=r_cfg.get("rationale", "Direct hardware protection contact fired."),
                    evidence_ids=direct_trip_evidence_ids or [f"trip_{event.event_id}"],
                    source_reference="Substation Safety & Protection Operating Procedure",
                    merge_key=r_cfg.get("merge_key", "SAFETY_PROTECTION_TRIP"),
                    supporting_rule_ids=["MNT-PROT-001"],
                    consequence_class=r_cfg.get("consequence_class", "SAFETY_CRITICAL"),
                    binding_vs_advisory="ADVISORY",
                    approved_by=r_cfg.get("approved_by", "Chief Protection Engineer"),
                    source_version=r_cfg.get("source_version", "2026.1"),
                    created_at_utc=current_time,
                )
            )

        # --- Rule 2: MNT-THERM-002 (P1 URGENT_INSPECTION / WITHIN_24H) ---
        if "top_oil_temperature" not in bad_signals and "MNT-THERM-002" in self.rules:
            # Physical limit exceedances trigger unconditionally across all assets (even unpromoted)
            limit_evs = [
                ev
                for ev in evidence_list
                if ev.category == AnomalyCategory.THERMAL_LIMIT
                or ev.condition_family == "THERMAL_LIMIT_EXCEEDANCE"
                or getattr(ev, "detector_id", "") in ("DET_THERMAL_LIMIT_ABSOLUTE", "DET_THERMAL_LIMIT_WARNING")
            ]
            # Model-derived deviations are strictly gated by thermal qualification
            model_evs = []
            if self.cusum_qualification != "DISABLED" and self.is_thermal_qualified:
                # Shadow-only detectors (e.g. CUSUM on an autocorrelated residual, which alarms on most
                # normal frames) never penalize OTHI, so they must not raise a P1 inspection either
                model_evs = [
                    ev
                    for ev in evidence_list
                    if ev.detector_id not in SHADOW_ONLY_DETECTORS
                    and (
                        ev.category == AnomalyCategory.THERMAL_DEVIATION
                        or ev.condition_family == "THERMAL_DEVIATION_UNEXPECTED"
                        or getattr(ev, "detector_id", "") in ("DET_THERMAL_CUSUM_DRIFT", "DET_THERMAL_RESIDUAL_BIAS")
                    )
                ]
            therm_evs = limit_evs + model_evs
            if therm_evs:
                r_cfg = self.rules["MNT-THERM-002"]
                rec_id = f"REC-{event.asset_id}-MNT-THERM-002"
                is_direct_limit = bool(limit_evs)
                title = "Direct Top-Oil Thermal Limit Exceedance" if is_direct_limit else r_cfg.get("title", "Thermal Model Deviation Inspection")
                rationale = "Direct physical top-oil temperature limit exceeded." if is_direct_limit else r_cfg.get("rationale", "Thermal model deviation detected on qualified asset.")
                fired_recommendations.append(
                    MaintenanceRecommendation(
                        recommendation_id=rec_id,
                        rule_id="MNT-THERM-002",
                        rule_version=r_cfg.get("version", "1.0.0"),
                        title=title,
                        priority=MaintenancePriority.P1_URGENT_INSPECTION,
                        priority_label="P1 URGENT_INSPECTION",
                        action_window=ActionWindow.WITHIN_24H,
                        window_provenance_type=ActionWindowProvenanceType.OPERATOR_POLICY,
                        window_source_reference=r_cfg.get("window_source_reference", "Utility CBM Manual Sec 4.2"),
                        advisory_wording=r_cfg.get("advisory_wording", "Arrange prompt inspection of cooling operation."),
                        rationale=rationale,
                        evidence_ids=[ev.evidence_id for ev in therm_evs],
                        source_reference="Condition-Based Maintenance Manual Sec 4.2",
                        merge_key=r_cfg.get("merge_key", "THERMAL_COOLING_STRESS"),
                        supporting_rule_ids=["MNT-THERM-002"],
                        consequence_class=r_cfg.get("consequence_class", "THERMAL_ACCELERATED_AGEING"),
                        binding_vs_advisory="ADVISORY",
                        approved_by=r_cfg.get("approved_by", "Substation Maintenance Superintendent"),
                        source_version=r_cfg.get("source_version", "2026.1"),
                        created_at_utc=current_time,
                    )
                )

        # --- Rule 3: MNT-FORE-003 (P1 WITHIN_24H or P3 MONITOR) ---
        # Gating check: Requires promoted model (is_model_promoted = True) and enabled projection
        if (
            self.is_model_promoted
            and scenario_projection is not None
            and scenario_projection.is_enabled
            and (
                scenario_projection.earliest_warning_crossing_minutes is not None
                or scenario_projection.earliest_critical_crossing_minutes is not None
            )
            and "MNT-FORE-003" in self.rules
        ):
            crossing_mins = (
                scenario_projection.earliest_critical_crossing_minutes
                if scenario_projection.earliest_critical_crossing_minutes is not None
                else scenario_projection.earliest_warning_crossing_minutes
            )
            is_critical_or_early = (
                scenario_projection.earliest_critical_crossing_minutes is not None
                or (crossing_mins is not None and crossing_mins <= 60)
            )
            priority = (
                MaintenancePriority.P1_URGENT_INSPECTION
                if is_critical_or_early
                else MaintenancePriority.P3_MONITOR
            )
            priority_lbl = "P1 URGENT_INSPECTION" if is_critical_or_early else "P3 MONITOR"
            window = ActionWindow.WITHIN_24H if is_critical_or_early else ActionWindow.MONITOR

            r_cfg = self.rules["MNT-FORE-003"]
            rec_id = f"REC-{event.asset_id}-MNT-FORE-003"
            fired_recommendations.append(
                MaintenanceRecommendation(
                    recommendation_id=rec_id,
                    rule_id="MNT-FORE-003",
                    rule_version=r_cfg.get("version", "1.0.0"),
                    title=r_cfg.get("title", "Thermal Scenario Threshold Exceedance"),
                    priority=priority,
                    priority_label=priority_lbl,
                    action_window=window,
                    window_provenance_type=ActionWindowProvenanceType.ENGINEERING_POLICY,
                    window_source_reference=r_cfg.get("window_source_reference", "Digital Twin Forecast Guide"),
                    advisory_wording=r_cfg.get("advisory_wording", "Review permissible load redistribution with operator."),
                    rationale=r_cfg.get("rationale", "Scenario projection indicates thermal limit crossing."),
                    evidence_ids=[f"forecast_cross_{crossing_mins}m"],
                    source_reference="Digital Twin 2-Hour Thermal Forecast Guide",
                    merge_key=r_cfg.get("merge_key", "THERMAL_PROJECTION"),
                    supporting_rule_ids=["MNT-FORE-003"],
                    consequence_class=r_cfg.get("consequence_class", "OPERATIONAL_OVERLOAD_RISK"),
                    binding_vs_advisory="ADVISORY",
                    approved_by=r_cfg.get("approved_by", "Asset Strategy Lead"),
                    source_version=r_cfg.get("source_version", "2026.1"),
                    created_at_utc=current_time,
                )
            )

        # --- Rule 4: MNT-PHASE-004 (P2 / NEXT_AUTHORIZED_MAINTENANCE_WINDOW) ---
        phase_bad = any(s in bad_signals for s in ("current_l1", "current_l2", "current_l3"))
        if not phase_bad and "MNT-PHASE-004" in self.rules:
            phase_evs = [
                ev
                for ev in evidence_list
                if ev.category == AnomalyCategory.PHASE_OR_NEUTRAL
                or ev.condition_family in ("PHASE_CURRENT_IMBALANCE", "NEUTRAL_CURRENT_EXCESS")
            ]
            if phase_evs:
                r_cfg = self.rules["MNT-PHASE-004"]
                rec_id = f"REC-{event.asset_id}-MNT-PHASE-004"
                fired_recommendations.append(
                    MaintenanceRecommendation(
                        recommendation_id=rec_id,
                        rule_id="MNT-PHASE-004",
                        rule_version=r_cfg.get("version", "1.0.0"),
                        title=r_cfg.get("title", "Phase Imbalance Maintenance"),
                        priority=MaintenancePriority.P2_PLANNED_ACTION,
                        priority_label="P2 PLANNED_ACTION",
                        action_window=ActionWindow.NEXT_AUTHORIZED_MAINTENANCE_WINDOW,
                        window_provenance_type=ActionWindowProvenanceType.OPERATOR_POLICY,
                        window_source_reference=r_cfg.get("window_source_reference", "Feeder Balancing Standard"),
                        advisory_wording=r_cfg.get("advisory_wording", "Inspect phase loading during next window."),
                        rationale=r_cfg.get("rationale", "Persistent current imbalance corroborated by neutral return."),
                        evidence_ids=[ev.evidence_id for ev in phase_evs],
                        source_reference="Feeder Phase Balancing Maintenance Standard",
                        merge_key=r_cfg.get("merge_key", "PHASE_NEUTRAL_IMBALANCE"),
                        supporting_rule_ids=["MNT-PHASE-004"],
                        consequence_class=r_cfg.get("consequence_class", "UNEVEN_HEATING_NEUTRAL_STRESS"),
                        binding_vs_advisory="ADVISORY",
                        approved_by=r_cfg.get("approved_by", "Distribution Operations Lead"),
                        source_version=r_cfg.get("source_version", "2026.1"),
                        created_at_utc=current_time,
                    )
                )

        # --- Rule 5: MNT-PF-005 (P3 / MONITOR) ---
        pf_bad = "power_factor_total" in bad_signals or "active_power_total" in bad_signals
        if not pf_bad and "MNT-PF-005" in self.rules:
            pf_evs = [
                ev
                for ev in evidence_list
                if ev.condition_family in ("LOW_POWER_FACTOR", "POWER_FACTOR_ANOMALY", "POWER_FACTOR_REACTIVE")
                or (ev.category == AnomalyCategory.VOLTAGE_PF_FREQUENCY and any(x in ev.detector_id.lower() for x in ("pf", "power_factor")))
            ]

            if pf_evs:
                r_cfg = self.rules["MNT-PF-005"]
                rec_id = f"REC-{event.asset_id}-MNT-PF-005"
                fired_recommendations.append(
                    MaintenanceRecommendation(
                        recommendation_id=rec_id,
                        rule_id="MNT-PF-005",
                        rule_version=r_cfg.get("version", "1.0.0"),
                        title=r_cfg.get("title", "Low Power Factor Review"),
                        priority=MaintenancePriority.P3_MONITOR,
                        priority_label="P3 MONITOR",
                        action_window=ActionWindow.MONITOR,
                        window_provenance_type=ActionWindowProvenanceType.ENGINEERING_POLICY,
                        window_source_reference=r_cfg.get("window_source_reference", "Reactive Power Guideline"),
                        advisory_wording=r_cfg.get("advisory_wording", "Investigate downstream reactive demand."),
                        rationale=r_cfg.get("rationale", "Downstream reactive demand without internal failure."),
                        evidence_ids=[ev.evidence_id for ev in pf_evs],
                        source_reference="Utility Reactive Power Management Guideline",
                        merge_key=r_cfg.get("merge_key", "POWER_FACTOR_REACTIVE"),
                        supporting_rule_ids=["MNT-PF-005"],
                        consequence_class=r_cfg.get("consequence_class", "REACTIVE_LOSSES"),
                        binding_vs_advisory="ADVISORY",
                        approved_by=r_cfg.get("approved_by", "Grid Modernization Engineer"),
                        source_version=r_cfg.get("source_version", "2026.1"),
                        created_at_utc=current_time,
                    )
                )

        # --- Rule 6: MNT-SENS-006 (P4 / MODEL_REVIEW) ---
        sens_evs = [
            ev
            for ev in evidence_list
            if ev.category in (AnomalyCategory.DATA_QUALITY, AnomalyCategory.SENSOR_PLAUSIBILITY)
        ]
        if sens_evs and "MNT-SENS-006" in self.rules:
            r_cfg = self.rules["MNT-SENS-006"]
            rec_id = f"REC-{event.asset_id}-MNT-SENS-006"
            fired_recommendations.append(
                MaintenanceRecommendation(
                    recommendation_id=rec_id,
                    rule_id="MNT-SENS-006",
                    rule_version=r_cfg.get("version", "1.0.0"),
                    title=r_cfg.get("title", "Sensor Plausibility Review"),
                    priority=MaintenancePriority.P4_DATA_OR_MODEL,
                    priority_label="P4 DATA_OR_MODEL",
                    action_window=ActionWindow.MODEL_REVIEW,
                    window_provenance_type=ActionWindowProvenanceType.ENGINEERING_POLICY,
                    window_source_reference=r_cfg.get("window_source_reference", "Sensor Validation Standard"),
                    advisory_wording=r_cfg.get("advisory_wording", "Inspect identified sensor and mapping."),
                    rationale=r_cfg.get("rationale", "Data plausibility fault detected. Model dependency suspended."),
                    evidence_ids=[ev.evidence_id for ev in sens_evs],
                    source_reference="Telemetry Data Governance & Sensor Validation Standard",
                    merge_key=r_cfg.get("merge_key", "SENSOR_PLAUSIBILITY_FAULT"),
                    supporting_rule_ids=["MNT-SENS-006"],
                    consequence_class=r_cfg.get("consequence_class", "DATA_QUALITY_DEGRADATION"),
                    binding_vs_advisory="ADVISORY",
                    approved_by=r_cfg.get("approved_by", "OT Systems Lead"),
                    source_version=r_cfg.get("source_version", "2026.1"),
                    created_at_utc=current_time,
                )
            )

        # --- Rule 7: MNT-MODEL-007 (P4 / MODEL_REVIEW) ---
        model_evs = [
            ev
            for ev in evidence_list
            if ev.condition_family in ("MODEL_CALIBRATION_DRIFT", "COVERAGE_DEGRADATION")
        ]
        if model_evs and "MNT-MODEL-007" in self.rules:
            r_cfg = self.rules["MNT-MODEL-007"]
            rec_id = f"REC-{event.asset_id}-MNT-MODEL-007"
            fired_recommendations.append(
                MaintenanceRecommendation(
                    recommendation_id=rec_id,
                    rule_id="MNT-MODEL-007",
                    rule_version=r_cfg.get("version", "1.0.0"),
                    title=r_cfg.get("title", "Thermal Model Calibration Review"),
                    priority=MaintenancePriority.P4_DATA_OR_MODEL,
                    priority_label="P4 DATA_OR_MODEL",
                    action_window=ActionWindow.MODEL_REVIEW,
                    window_provenance_type=ActionWindowProvenanceType.ENGINEERING_POLICY,
                    window_source_reference=r_cfg.get("window_source_reference", "Model Validation Policy"),
                    advisory_wording=r_cfg.get("advisory_wording", "Review calibration and input mapping."),
                    rationale=r_cfg.get("rationale", "Thermal residual drift or coverage degradation detected."),
                    evidence_ids=[ev.evidence_id for ev in model_evs],
                    source_reference="Digital Twin Model Calibration & Validation Policy",
                    merge_key=r_cfg.get("merge_key", "MODEL_CALIBRATION_DRIFT"),
                    supporting_rule_ids=["MNT-MODEL-007"],
                    consequence_class=r_cfg.get("consequence_class", "MODEL_UNCERTAINTY"),
                    binding_vs_advisory="ADVISORY",
                    approved_by=r_cfg.get("approved_by", "Chief Data Scientist"),
                    source_version=r_cfg.get("source_version", "2026.1"),
                    created_at_utc=current_time,
                )
            )

        # --- Rule 8: MNT-OIL-008 (P2 / NEXT_AUTHORIZED_MAINTENANCE_WINDOW) ---
        oil_evs = [
            ev
            for ev in evidence_list
            if getattr(ev, "detector_id", "") in (
                "DET_OIL_LEVEL_DECLINING_TREND",
                "DET_OIL_LEVEL_INDICATOR",
                "DET_OIL_LEVEL_GAUGE_STUCK",
                "DET_PROT_MOG_ALARM",
            )
            or ev.condition_family in ("OIL_LEVEL_DECLINING_TREND", "OIL_LEVEL_LOW")
        ]
        if oil_evs and "MNT-OIL-008" in self.rules:
            r_cfg = self.rules["MNT-OIL-008"]
            rec_id = f"REC-{event.asset_id}-MNT-OIL-008"
            fired_recommendations.append(
                MaintenanceRecommendation(
                    recommendation_id=rec_id,
                    rule_id="MNT-OIL-008",
                    rule_version=r_cfg.get("version", "1.0.0"),
                    title=r_cfg.get("title", "Oil Level Trend / Suspected Loss Inspection"),
                    priority=MaintenancePriority.P2_PLANNED_ACTION,
                    priority_label="P2 PLANNED_ACTION",
                    action_window=ActionWindow.NEXT_AUTHORIZED_MAINTENANCE_WINDOW,
                    window_provenance_type=ActionWindowProvenanceType.OPERATOR_POLICY,
                    window_source_reference=r_cfg.get("window_source_reference", "Utility CBM Standard"),
                    advisory_wording=r_cfg.get("advisory_wording", "Inspect conservator/tank seals and level gauge."),
                    rationale=r_cfg.get("rationale", "Persistent decline in oil level indicates suspected loss requiring inspection."),
                    evidence_ids=[ev.evidence_id for ev in oil_evs],
                    source_reference="Distribution Transformer Maintenance Standard Sec 5.1",
                    merge_key=r_cfg.get("merge_key", "OIL_LEVEL_LOSS_TREND"),
                    supporting_rule_ids=["MNT-OIL-008"],
                    consequence_class=r_cfg.get("consequence_class", "INSULATION_OIL_LOSS"),
                    binding_vs_advisory="ADVISORY",
                    approved_by=r_cfg.get("approved_by", "Substation Maintenance Superintendent"),
                    source_version=r_cfg.get("source_version", "2026.1"),
                    created_at_utc=current_time,
                )
            )

        # --- Rule 9: MNT-PRESS-009 (P1 / WITHIN_24H) ---
        press_evs = [
            ev
            for ev in evidence_list
            if getattr(ev, "detector_id", "") in (
                "DET_PRESSURE_HIGH_ALARM",
                "DET_PRESSURE_ALARM_CONTACT",
                "DET_PRESSURE_LOW_ALARM",
                "DET_PRESSURE_RELIEF_OPERATED",
            )
            or ev.condition_family in ("SEALED_TANK_PRESSURE",)
        ]
        if press_evs and "MNT-PRESS-009" in self.rules:

            r_cfg = self.rules["MNT-PRESS-009"]
            rec_id = f"REC-{event.asset_id}-MNT-PRESS-009"
            fired_recommendations.append(
                MaintenanceRecommendation(
                    recommendation_id=rec_id,
                    rule_id="MNT-PRESS-009",
                    rule_version=r_cfg.get("version", "1.0.0"),
                    title=r_cfg.get("title", "Sealed Tank Pressure Anomaly Review"),
                    priority=MaintenancePriority.P1_URGENT_INSPECTION,
                    priority_label="P1 URGENT_INSPECTION",
                    action_window=ActionWindow.WITHIN_24H,
                    window_provenance_type=ActionWindowProvenanceType.OPERATOR_POLICY,
                    window_source_reference=r_cfg.get("window_source_reference", "Sealed Transformer Manual"),
                    advisory_wording=r_cfg.get("advisory_wording", "Inspect corrugated tank fin expansion and pressure gauge."),
                    rationale=r_cfg.get("rationale", "Sealed tank gauge pressure exceeds safe operational band."),
                    evidence_ids=[ev.evidence_id for ev in press_evs],
                    source_reference="Sealed Distribution Transformer Operating Manual Sec 3.4",
                    merge_key=r_cfg.get("merge_key", "SEALED_TANK_PRESSURE"),
                    supporting_rule_ids=["MNT-PRESS-009"],
                    consequence_class=r_cfg.get("consequence_class", "TANK_OVERPRESSURE_RISK"),
                    binding_vs_advisory="ADVISORY",
                    approved_by=r_cfg.get("approved_by", "Substation Maintenance Superintendent"),
                    source_version=r_cfg.get("source_version", "2026.1"),
                    created_at_utc=current_time,
                )
            )

        # Preserve creation timestamp and acknowledgement metadata from matching prior active recommendations
        for prev_rec in (previous_recommendations or []):
            for idx, r in enumerate(fired_recommendations):
                if r.rule_id == prev_rec.rule_id or r.merge_key == prev_rec.merge_key:
                    fired_recommendations[idx] = r.model_copy(
                        update={
                            "created_at_utc": prev_rec.created_at_utc,
                            "acknowledged": prev_rec.acknowledged if not r.acknowledged else True,
                            "acknowledged_at_utc": prev_rec.acknowledged_at_utc if not r.acknowledged_at_utc else r.acknowledged_at_utc,
                            "acknowledged_by": prev_rec.acknowledged_by if not r.acknowledged_by else r.acknowledged_by,
                        }
                    )

        # 3. Merge compatible recommendations sharing a merge_key
        merged_by_key: Dict[str, List[MaintenanceRecommendation]] = {}
        for rec in fired_recommendations:
            if rec.merge_key not in merged_by_key:
                merged_by_key[rec.merge_key] = []
            merged_by_key[rec.merge_key].append(rec)

        # 4. Apply feedback lifecycle (acknowledgements, dismissals/recurrence, overrides)
        active_acks = self.feedback_ledger.get_active_acknowledgements(asset_id=event.asset_id)
        active_dismissals = self.feedback_ledger.get_active_dismissals(asset_id=event.asset_id)
        active_overrides = self.feedback_ledger.get_active_overrides(
            asset_id=event.asset_id, current_time=current_time
        )
        ev_time_map = {
            ev.evidence_id: (ev.event_time_utc if ev.event_time_utc.tzinfo else ev.event_time_utc.replace(tzinfo=timezone.utc))
            for ev in evidence_list
        }


        final_recommendations: List[MaintenanceRecommendation] = []
        for key, rec_group in merged_by_key.items():
            if len(rec_group) == 1:
                merged_rec = rec_group[0]
            else:
                # Merge multiple recommendations sharing the same key:
                # Select strictest priority and strictest action window
                best_prio = min((r.priority for r in rec_group), key=lambda p: PRIORITY_ORDER[p])
                best_win = min((r.action_window for r in rec_group), key=lambda w: WINDOW_ORDER[w])

                all_ev_ids: List[str] = []
                all_rules: List[str] = []
                for r in rec_group:
                    all_ev_ids.extend(r.evidence_ids)
                    all_rules.extend(r.supporting_rule_ids)

                lead_rec = min(rec_group, key=lambda r: PRIORITY_ORDER[r.priority])
                merged_rec = lead_rec.model_copy(
                    update={
                        "priority": best_prio,
                        "priority_label": best_prio.name.replace("_", " "),
                        "action_window": best_win,
                        "evidence_ids": sorted(set(all_ev_ids)),
                        "supporting_rule_ids": sorted(set(all_rules)),
                    }
                )

            # Check dismissal & recurrence
            dismissal = (
                active_dismissals.get(merged_rec.recommendation_id)
                or active_dismissals.get(merged_rec.merge_key)
                or active_dismissals.get(merged_rec.rule_id)
            )
            if dismissal is not None:
                d_ts = dismissal.timestamp_utc
                if d_ts.tzinfo is None:
                    d_ts = d_ts.replace(tzinfo=timezone.utc)

                # Check if all contributing evidence was emitted at or before dismissal
                ev_timestamps = [
                    ev_time_map[eid]
                    for eid in merged_rec.evidence_ids
                    if eid in ev_time_map
                ]
                latest_ev_ts = max(ev_timestamps) if ev_timestamps else current_time

                if latest_ev_ts <= d_ts:
                    # Specific instance is dismissed/resolved; suppress from active display
                    continue
                # If latest_ev_ts > d_ts or condition recurred after dismissal:
                # Retain recommendation as a newly generated active instance

            # Check authorized override
            override = (
                active_overrides.get(merged_rec.recommendation_id)
                or active_overrides.get(merged_rec.merge_key)
                or active_overrides.get(merged_rec.rule_id)
            )
            if override is not None:
                role = override.authorized_role or override.operator_id
                rationale_text = override.rationale or override.notes or "Authorized operating override"
                merged_rec = merged_rec.model_copy(
                    update={
                        "advisory_wording": f"[AUTHORIZED OVERRIDE by {role}]: {rationale_text}"
                    }
                )

            # Check acknowledgment
            ack = (
                active_acks.get(merged_rec.recommendation_id)
                or active_acks.get(merged_rec.merge_key)
                or active_acks.get(merged_rec.rule_id)
            )
            if ack is not None:
                ack_ts = ack.timestamp_utc
                if ack_ts.tzinfo is None:
                    ack_ts = ack_ts.replace(tzinfo=timezone.utc)
                merged_rec = merged_rec.model_copy(
                    update={
                        "acknowledged": True,
                        "acknowledged_at_utc": ack_ts,
                        "acknowledged_by": ack.operator_id,
                    }
                )

            final_recommendations.append(merged_rec)

        # 5. Sort final recommendations by priority order (P0 first, then P1, P2, P3, P4)
        final_recommendations.sort(key=lambda r: PRIORITY_ORDER[r.priority])

        return final_recommendations

