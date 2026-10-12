"""Phase 6.5 / Batch 4 — Deterministic Review Flag Engine.

REVIEW FLAG — Observed behaviour warrants human review; the available evidence
does not support a qualified anomaly conclusion.

Enforces:
- Four strictly independent dimensions: Condition, Observability, Lifecycle, Human Workflow.
- Acknowledgement or dismissal records a human workflow decision; it does NOT clear underlying physical evidence.
- Deterministic review IDs, deduplication, and expected-revision checks.
- Zero wall-clock `now()` dependencies: pure function of event-time and stream position.
- Invariance: Review flags never alter OTHI, model capabilities, CUSUM gates, or protection events.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.engine.anomaly_detectors import is_watch_level_evidence
from app.models.anomaly import AnomalyCategory, AnomalyEpisode, EvidenceItem
from app.models.review import (
    ConditionState,
    HumanWorkflowState,
    ObservabilityState,
    ResidualTriggerPolicy,
    ReviewConditionFamily,
    ReviewFlagRecord,
    ReviewLifecycleState,
)


def build_review_id(asset_id: str, family: ReviewConditionFamily, target: str) -> str:
    """Generate deterministic review identifier."""
    clean_target = target.replace("/", "_").replace(" ", "_").lower()
    return f"rev_{asset_id}_{family.value.lower()}_{clean_target}"


def evaluate_residual_trigger_promotion_gate(
    candidate: ResidualTriggerPolicy,
) -> ResidualTriggerPolicy:
    """Evaluate candidate residual trigger against the five Section 7 CPRI promotion gates.

    Promotion requires ALL of:
    (a) Candidate rule selected using FIT/CAL only and versioned as separate policy artifact;
    (b) CAL has >= 21 eligible benign asset-days per enabled asset;
    (c) Predefined challenge cases pass without missed events, delay, fragmentation;
    (d) Workload budget met (<= 1 unmatched flag per 7 eligible asset-days);
    (e) Sealed TEST evaluation passed once and not used for tuning.
    """
    reasons: list[str] = []

    if not candidate.policy_version or candidate.policy_version == "unversioned":
        reasons.append("POLICY_ARTIFACT_NOT_VERSIONED")

    if candidate.benign_cal_asset_days < candidate.min_benign_cal_asset_days_required:
        reasons.append(
            f"INSUFFICIENT_BENIGN_CAL_DAYS: {candidate.benign_cal_asset_days:.1f} < "
            f"{candidate.min_benign_cal_asset_days_required:.1f}"
        )

    if candidate.unmatched_flags_per_7_asset_days > candidate.max_workload_budget_per_7_asset_days:
        reasons.append(
            f"WORKLOAD_BUDGET_EXCEEDED: {candidate.unmatched_flags_per_7_asset_days:.2f} > "
            f"{candidate.max_workload_budget_per_7_asset_days:.2f}"
        )

    if not candidate.challenge_cases_passed:
        reasons.append("CHALLENGE_CASES_FAILED_OR_UNTESTED")

    if not candidate.sealed_test_passed:
        reasons.append("SEALED_TEST_FAILED_OR_UNTESTED")

    is_qual = len(reasons) == 0
    return candidate.model_copy(
        update={
            "is_qualified": is_qual,
            "gate_failure_reasons": reasons,
        }
    )


class ReviewFlagEngine:
    """Stateful deterministic engine evaluating Review Flags."""

    def __init__(
        self,
        asset_id: str,
        policy_version: str = "review_flag_v1_0",
        clearing_steps_required: int = 2,
        closed_steps_required: int = 4,
        residual_policy: Optional[ResidualTriggerPolicy] = None,
    ) -> None:
        self.asset_id = str(asset_id)
        self.policy_version = str(policy_version)
        self.clearing_steps_required = int(clearing_steps_required)
        self.closed_steps_required = int(closed_steps_required)
        self.residual_policy = residual_policy
        self._quiet_steps_by_review: Dict[str, int] = {}
        self._processed_idempotency_keys: Set[str] = set()

    def reset(self) -> None:
        """Reset internal recovery tracking."""
        self._quiet_steps_by_review.clear()
        self._processed_idempotency_keys.clear()

    def evaluate_step(
        self,
        event_time_utc: datetime,
        stream_position: int,
        evidence_items: List[EvidenceItem],
        open_episodes: List[AnomalyEpisode],
        previous_reviews: List[ReviewFlagRecord],
        is_gap: bool = False,
    ) -> List[ReviewFlagRecord]:
        """Step review flag state deterministically on one canonical event.

        Args:
            event_time_utc: Canonical event timestamp in UTC.
            stream_position: Monotonic stream sequence number.
            evidence_items: Newly emitted evidence items from current event.
            open_episodes: Currently active qualified anomaly episodes.
            previous_reviews: Active review records from prior twin state.
            is_gap: Whether monitoring gap exceeded (suspends recovery accumulation).

        Returns:
            List[ReviewFlagRecord]: Updated list of review records.
        """
        review_map: Dict[str, ReviewFlagRecord] = {r.review_id: r for r in previous_reviews}
        triggered_review_ids: Set[str] = set()

        # 1. Inspect evidence items for eligible behavioural conditions
        for ev in evidence_items:
            # Watch-level evidence scores OTHI only; it does not warrant a review flag
            if is_watch_level_evidence(ev):
                continue
            # Map evidence to candidate condition family and target
            fam: Optional[ReviewConditionFamily] = None
            target: Optional[str] = None

            if ev.category == AnomalyCategory.SENSOR_PLAUSIBILITY:
                fam = ReviewConditionFamily.ENGINEERING_PLAUSIBILITY
                target = "sensor_top_oil"
            elif ev.category in (AnomalyCategory.PHASE_OR_NEUTRAL, "ELECTRICAL_UNBALANCE", "PHASE_OR_NEUTRAL"):
                fam = ReviewConditionFamily.ELECTRICAL_UNBALANCE_ADVISORY
                target = "electrical_imbalance"
            elif ev.category == AnomalyCategory.THERMAL_DEVIATION:
                if self.residual_policy is not None and self.residual_policy.is_qualified:
                    fam = ReviewConditionFamily.THERMAL_BEHAVIOUR_UNVERIFIED
                    target = "thermal_residual"
                else:
                    # Automatic residual flags remain strictly disabled by default until promotion gate is passed
                    continue

            if fam is None or target is None:
                continue

            rev_id = build_review_id(self.asset_id, fam, target)
            triggered_review_ids.add(rev_id)
            self._quiet_steps_by_review[rev_id] = 0  # Reset quiet recovery steps

            if rev_id in review_map:
                existing = review_map[rev_id]
                # Reopen if previously closed and physical condition recurs
                new_lifecycle = (
                    ReviewLifecycleState.OPEN
                    if existing.lifecycle_state in (ReviewLifecycleState.CLOSED, ReviewLifecycleState.CLEARING)
                    else existing.lifecycle_state
                )
                new_workflow = (
                    HumanWorkflowState.UNACKNOWLEDGED
                    if existing.lifecycle_state == ReviewLifecycleState.CLOSED
                    else existing.workflow_state
                )
                evidence_ids = list(dict.fromkeys(existing.supporting_evidence_ids + [ev.evidence_id]))

                review_map[rev_id] = existing.model_copy(
                    update={
                        "lifecycle_state": new_lifecycle,
                        "workflow_state": new_workflow,
                        "last_updated_event_time_utc": event_time_utc,
                        "logical_stream_position": stream_position,
                        "supporting_evidence_ids": evidence_ids,
                        "revision": existing.revision + 1,
                    }
                )
            else:
                # Create brand new review record
                review_map[rev_id] = ReviewFlagRecord(
                    review_id=rev_id,
                    asset_id=self.asset_id,
                    condition_family=fam,
                    target=target,
                    condition=ConditionState.INSUFFICIENT_EVIDENCE,
                    observability=ObservabilityState.CURRENT,
                    lifecycle_state=ReviewLifecycleState.OPEN,
                    workflow_state=HumanWorkflowState.UNACKNOWLEDGED,
                    revision=1,
                    created_event_time_utc=event_time_utc,
                    last_updated_event_time_utc=event_time_utc,
                    logical_stream_position=stream_position,
                    supporting_evidence_ids=[ev.evidence_id],
                    policy_version=self.policy_version,
                )

        # 2. Check for Superseding by Qualified Anomalies
        for rev_id, rec in list(review_map.items()):
            if rec.lifecycle_state in (ReviewLifecycleState.OPEN, ReviewLifecycleState.CLEARING):
                matching_ep = None
                for ep in open_episodes:
                    is_active = (ep.state.value != "CLOSED") if hasattr(ep.state, "value") else (str(ep.state) != "CLOSED")
                    if is_active:
                        if ep.category == AnomalyCategory.SENSOR_PLAUSIBILITY and "sensor" in rec.target:
                            matching_ep = ep
                            break
                        elif ep.category == AnomalyCategory.PHASE_OR_NEUTRAL and "imbalance" in rec.target:
                            matching_ep = ep
                            break
                        elif ep.category == AnomalyCategory.THERMAL_DEVIATION and "thermal" in rec.target:
                            matching_ep = ep
                            break

                if matching_ep is not None:
                    review_map[rev_id] = rec.model_copy(
                        update={
                            "lifecycle_state": ReviewLifecycleState.SUPERSEDED,
                            "condition": ConditionState.QUALIFIED_ANOMALY,
                            "last_updated_event_time_utc": event_time_utc,
                            "logical_stream_position": stream_position,
                            "superseded_by_anomaly_id": matching_ep.episode_id,
                            "revision": rec.revision + 1,
                        }
                    )

        # 3. Advance quiet recovery counters for reviews NOT triggered in this step
        if not is_gap:
            for rev_id, rec in list(review_map.items()):
                if rev_id not in triggered_review_ids and rec.lifecycle_state in (
                    ReviewLifecycleState.OPEN,
                    ReviewLifecycleState.CLEARING,
                ):
                    quiet = self._quiet_steps_by_review.get(rev_id, 0) + 1
                    self._quiet_steps_by_review[rev_id] = quiet

                    if quiet >= self.closed_steps_required:
                        # Full quiet recovery reached -> CLOSED
                        review_map[rev_id] = rec.model_copy(
                            update={
                                "lifecycle_state": ReviewLifecycleState.CLOSED,
                                "condition": ConditionState.NORMAL,
                                "last_updated_event_time_utc": event_time_utc,
                                "logical_stream_position": stream_position,
                                "resolution_reason": f"Physical evidence cleared over {quiet} consecutive observations.",
                                "revision": rec.revision + 1,
                            }
                        )
                    elif quiet >= self.clearing_steps_required and rec.lifecycle_state == ReviewLifecycleState.OPEN:
                        # Partial quiet recovery reached -> CLEARING
                        review_map[rev_id] = rec.model_copy(
                            update={
                                "lifecycle_state": ReviewLifecycleState.CLEARING,
                                "last_updated_event_time_utc": event_time_utc,
                                "logical_stream_position": stream_position,
                                "revision": rec.revision + 1,
                            }
                        )

        return list(review_map.values())

    def apply_feedback_mutation(
        self,
        reviews: List[ReviewFlagRecord],
        review_id: str,
        action: str,
        actor_id: str,
        rationale: Optional[str] = None,
        expected_revision: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        event_time_utc: Optional[datetime] = None,
        stream_position: Optional[int] = None,
    ) -> List[ReviewFlagRecord]:
        """Apply human workflow feedback mutation deterministically.

        Acknowledgement/dismissal mutates HumanWorkflowState while preserving ReviewLifecycleState.
        """
        if idempotency_key and idempotency_key in self._processed_idempotency_keys:
            # Idempotent replay: return unchanged reviews
            return list(reviews)

        clean_action = str(action).strip().upper()
        actor = str(actor_id).strip()

        updated_list: List[ReviewFlagRecord] = []
        found = False

        for rec in reviews:
            if rec.review_id != review_id:
                updated_list.append(rec)
                continue

            ts = event_time_utc or rec.last_updated_event_time_utc
            pos = stream_position if stream_position is not None else rec.logical_stream_position

            found = True
            if expected_revision is not None and rec.revision != expected_revision:
                raise ValueError(
                    f"Conflict on ReviewFlag '{review_id}': expected revision {expected_revision}, "
                    f"but active revision is {rec.revision}."
                )

            new_workflow = rec.workflow_state
            new_lifecycle = rec.lifecycle_state
            res_reason = rec.resolution_reason

            if clean_action == "ACKNOWLEDGE":
                new_workflow = HumanWorkflowState.ACKNOWLEDGED
            elif clean_action == "DISMISS":
                new_workflow = HumanWorkflowState.DISMISSED
            elif clean_action == "RESOLVE":
                new_lifecycle = ReviewLifecycleState.CLOSED
                res_reason = rationale or "Resolved by operator investigation."
            elif clean_action == "REOPEN":
                new_lifecycle = ReviewLifecycleState.OPEN
                new_workflow = HumanWorkflowState.UNACKNOWLEDGED
                res_reason = None
            else:
                raise ValueError(f"Unsupported review action '{clean_action}'.")

            updated_record = rec.model_copy(
                update={
                    "workflow_state": new_workflow,
                    "lifecycle_state": new_lifecycle,
                    "revision": rec.revision + 1,
                    "actor_id": actor,
                    "rationale": rationale or rec.rationale,
                    "resolution_reason": res_reason,
                    "last_updated_event_time_utc": ts,
                    "logical_stream_position": pos,
                    "idempotency_key": idempotency_key,
                }
            )
            updated_list.append(updated_record)

        if not found:
            raise KeyError(f"ReviewFlag '{review_id}' not found.")

        if idempotency_key:
            self._processed_idempotency_keys.add(idempotency_key)

        return updated_list
