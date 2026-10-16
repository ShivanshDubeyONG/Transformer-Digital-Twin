from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    AppState,
    get_app_state,
    get_capability_evaluator,
    get_reducer,
    get_replay_engine,
    get_storage,
)
from app.api.errors import ReplayException
from app.api.schemas import ReplayControlRequest, ReplayStatusResponse
from app.core.registry import CPRI_SYNTHETIC_ASSET_RATINGS
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import assemble_fact_bundle
from app.engine.reducer import TwinReducer
from app.engine.replay import OPERATOR_INJECTED_FLAG, ReplayEngine
from app.models.capability import CapabilityTier

import os
from pathlib import Path
from app.models.telemetry import CanonicalEvent

router = APIRouter(prefix="", tags=["Replay"])


def _find_data_file(relative_path: str) -> Path | None:
    """Find data file checking cwd, repo root, and /app container path."""
    p1 = Path(relative_path)
    if p1.exists():
        return p1
    p2 = Path(__file__).resolve().parents[4] / relative_path
    if p2.exists():
        return p2
    p3 = Path("/app") / relative_path
    if p3.exists():
        return p3
    return None


def ensure_dataset_loaded(
    storage: StorageEngine | None,
    replay_engine: ReplayEngine,
    asset_id: str = "DT-TRIPURA-001",
) -> int:
    """Ensure canonical events are populated into storage and replay engine."""
    if len(replay_engine._events) > 0 and replay_engine.asset_id == asset_id:
        return len(replay_engine._events)

    replay_engine.asset_id = asset_id

    if storage is None:
        return 0

    # Only dataset telemetry counts as "already loaded"; stored operator-injected events must not
    # stop the dataset from loading (the replay would otherwise consist of the injected event alone).
    events_in_storage = [
        ev
        for ev in storage.get_canonical_events(asset_id=asset_id, limit=64)
        if OPERATOR_INJECTED_FLAG not in ev.event_quality_flags
    ]
    max_frames = int(os.getenv("MAX_REPLAY_FRAMES", "1000"))
    if not events_in_storage and asset_id in CPRI_SYNTHETIC_ASSET_RATINGS:
        # CPRI synthetic assets replay their CAL partition only; the TEST partition is reserved
        # for one-shot model evaluation. Oracle y_* labels never enter the runtime stream.
        cal_parquet = _find_data_file("data/processed/cpri_v3_calibration.parquet")
        if cal_parquet:
            import gc
            import pandas as pd
            from app.adapters.cpri_v3 import CPRIv3SourceAdapter
            df = pd.read_parquet(cal_parquet, filters=[("meta_transformer_id", "==", asset_id)])
            df = df.drop(columns=[c for c in df.columns if c.startswith("y_")])
            if max_frames > 0 and len(df) > max_frames:
                df = df.head(max_frames)
            adapter = CPRIv3SourceAdapter()
            events = [
                adapter.transform_record(
                    r,
                    asset_id=asset_id,
                    source_uri="data/processed/cpri_v3_calibration.parquet",
                    source_record_id=f"cal_{asset_id}_{i}",
                )
                for i, r in enumerate(df.to_dict("records"))
            ]
            storage.insert_canonical_events(events)
            del events, df
            gc.collect()
    elif not events_in_storage and (asset_id in ("DT-01", "DT-02", "DT-03", "DT-04") or "gridpulse" in str(asset_id).lower()):
        # Candidate synthetic assets replay their CAL partition only; the TEST partition is reserved
        # for one-shot evaluation. Ingests via GridPulseSyntheticAdapter into immutable CanonicalEvents.
        candidate_csv = _find_data_file("data/candidates/gridpulse_synthetic_v1/gridpulse_synthetic_30min.csv")
        if not candidate_csv:
            candidate_csv = _find_data_file("data/gridpulse_synthetic_30min.csv")
        if candidate_csv:
            import gc
            import pandas as pd
            from app.adapters.gridpulse_synthetic import GridPulseSyntheticAdapter
            df_full = pd.read_csv(candidate_csv, low_memory=False)
            df_asset = df_full[(df_full["asset_id"] == asset_id) & (df_full["partition"] == "CAL")].copy()
            if df_asset.empty:
                raise ReplayException(f"No CAL partition records found for candidate asset {asset_id} in {candidate_csv}")
            df_asset = df_asset.sort_values("timestamp_utc").reset_index(drop=True)
            if max_frames > 0 and len(df_asset) > max_frames:
                df_asset = df_asset.head(max_frames)
            adapter = GridPulseSyntheticAdapter()
            events = [
                adapter.transform_record(
                    r,
                    asset_id=asset_id,
                    source_uri=str(candidate_csv),
                    source_record_id=f"cal_{asset_id}_{i}",
                )
                for i, r in enumerate(df_asset.to_dict("records"))
            ]
            storage.insert_canonical_events(events)
            del events, df_full, df_asset
            gc.collect()
        else:
            raise ReplayException(
                f"Candidate dataset gridpulse_synthetic_30min.csv not found for asset {asset_id}. "
                "Explicit failure prevents silent fallback to CPRI baseline."
            )
    elif not events_in_storage:
        canon_events_file = _find_data_file("data/processed/canonical_events.parquet")
        canon_meas_file = _find_data_file("data/processed/canonical_measurements.parquet")
        if canon_events_file and canon_meas_file:
            storage.import_from_parquet("canonical_events", canon_events_file)
            storage.import_from_parquet("canonical_measurements", canon_meas_file)
        else:
            test_parquet = _find_data_file("data/processed/tripura_test.parquet")
            mapping_file = _find_data_file("backend/app/adapters/tripura_map.yaml")
            if test_parquet and mapping_file:
                import pandas as pd
                from app.adapters.tripura import TripuraCSVAdapter
                df = pd.read_parquet(test_parquet)
                adapter = TripuraCSVAdapter(mapping_file=mapping_file)
                records = df.to_dict("records")
                events = [adapter.transform_record(r, asset_id=asset_id) for r in records]
                storage.insert_canonical_events(events)

    count = replay_engine.load_from_storage()
    return count


def _restart_reducer(app_state: AppState, reducer: TwinReducer, target_asset: str | None = None) -> TwinReducer:
    """Give replay a clean reducer: rebuild all stateful engines when possible, else reset the thermal gate."""
    target = target_asset or (app_state.replay_engine.asset_id if app_state.replay_engine else app_state.settings.default_asset_id)
    if app_state.reducer_factory is not None:
        try:
            app_state.reducer = app_state.reducer_factory(target)
        except TypeError:
            app_state.reducer = app_state.reducer_factory()
        return app_state.reducer
    reducer.reset()
    return reducer


def _build_status_response(
    replay_engine: ReplayEngine,
    app_state: AppState,
) -> ReplayStatusResponse:
    """Build standardized ReplayStatusResponse."""
    progress = replay_engine.get_progress()
    current_state = app_state.current_state

    if progress["is_running"]:
        status_label = "running"
    elif progress["is_paused"]:
        status_label = "paused"
    elif progress["is_finished"] and progress["total_events"] > 0:
        status_label = "completed"
    elif progress["cursor"] == 0:
        status_label = "reset"
    else:
        status_label = "idle"

    # Current event time is only valid if at least 1 event has been processed
    curr_dt = None
    if progress["cursor"] > 0 and progress["cursor"] <= len(replay_engine._events):
        last_ev = replay_engine._events[progress["cursor"] - 1]
        curr_dt = last_ev.event_time_utc
        if curr_dt.tzinfo is None:
            curr_dt = curr_dt.replace(tzinfo=timezone.utc)

    highest_tier = (
        app_state.latest_fact_bundle.capabilities.highest_tier
        if app_state.latest_fact_bundle
        else (CapabilityTier.C0_INTEGRITY if current_state else None)
    )

    return ReplayStatusResponse(
        status=status_label,
        current_time_utc=curr_dt,
        speed_multiplier=progress["speed_multiplier"],
        processed_events=progress["cursor"],
        total_events=progress["total_events"],
        is_completed=progress["is_finished"] and progress["total_events"] > 0,
        current_state_sequence=current_state.state_sequence if current_state else None,
        highest_tier=highest_tier,
    )


@router.get(
    "/replay",
    response_model=ReplayStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get deterministic chronological replay status",
    description="Returns current deterministic chronological replay status and position.",
)
async def get_replay_status(
    app_state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
    replay_engine: ReplayEngine = Depends(get_replay_engine),
) -> ReplayStatusResponse:
    """Fetch current playback status of the deterministic replay engine."""
    if not replay_engine._events and storage is not None:
        target_asset = app_state.settings.default_asset_id if app_state and app_state.settings else "DT-TRIPURA-001"
        ensure_dataset_loaded(storage, replay_engine, target_asset)

    return _build_status_response(replay_engine, app_state)


@router.post(
    "/replay",
    response_model=ReplayStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Control deterministic chronological replay",
    description=(
        "Controls historical replay playback. Actions: 'start', 'step', 'pause', "
        "'resume', 'reset', 'seek'. Advancing replay steps events sequentially into "
        "the state transition reducer and updates active twin state and FactBundle."
    ),
)
async def control_replay(
    payload: ReplayControlRequest,
    app_state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
    reducer: TwinReducer = Depends(get_reducer),
    replay_engine: ReplayEngine = Depends(get_replay_engine),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> ReplayStatusResponse:
    """Execute playback action on the deterministic replay engine."""
    action = payload.action
    target_asset = payload.asset_id or (app_state.settings.default_asset_id if app_state and app_state.settings else "DT-TRIPURA-001")

    # If asset changed, reload dataset and reinitialize reducer & capability evaluator
    if payload.asset_id and payload.asset_id != replay_engine.asset_id:
        replay_engine.start_time = payload.start_time_utc
        replay_engine.end_time = payload.end_time_utc
        ensure_dataset_loaded(storage, replay_engine, target_asset)
        from app.api.deps import build_runtime_reducer
        from app.core.registry import resolve_asset_profile, resolve_model_artifact
        profile = resolve_asset_profile(asset_id=target_asset)
        artifact = resolve_model_artifact(asset_id=target_asset)
        is_promoted = artifact.parameters is not None and artifact.promotion.status == "PROMOTED"
        app_state.reducer = build_runtime_reducer(
            settings=app_state.settings,
            feedback_ledger=app_state.feedback_ledger,
            asset_id=target_asset,
            storage=storage,
        )
        app_state.profile = profile
        app_state.model_artifact = artifact
        app_state.capability_evaluator = CapabilityEvaluator(
            profile=profile,
            expected_cadence_s=profile.expected_cadence_s,
            evaluation_window_s=app_state.settings.evaluation_window_s,
            is_model_promoted=is_promoted,
            qualification=artifact.qualification if is_promoted else None,
            model_version=artifact.model_version if is_promoted else "uncalibrated",
        )
        capability_evaluator = app_state.capability_evaluator
        app_state.current_state = None
        app_state.latest_fact_bundle = None
        if app_state.feedback_ledger is not None:
            app_state.feedback_ledger.clear(target_asset)
        replay_engine.reset(clear_time_bounds=(payload.start_time_utc is None and payload.end_time_utc is None))
    elif not replay_engine._events and storage is not None:
        ensure_dataset_loaded(storage, replay_engine, target_asset)

    if app_state.reducer is not None:
        reducer = app_state.reducer
    if app_state.capability_evaluator is not None:
        capability_evaluator = app_state.capability_evaluator

    # Configure time bounds if requested
    if payload.start_time_utc is not None or payload.end_time_utc is not None:
        replay_engine.start_time = payload.start_time_utc
        replay_engine.end_time = payload.end_time_utc
        replay_engine.load_from_storage()

    # Configure speed multiplier
    replay_engine.speed_multiplier = payload.speed_multiplier

    if action == "start":
        ensure_dataset_loaded(storage, replay_engine, target_asset)
        replay_engine.reset()
        replay_engine._is_running = True
        replay_engine._is_paused = False
        app_state.current_state = None
        app_state.latest_fact_bundle = None
        if app_state.feedback_ledger is not None:
            app_state.feedback_ledger.clear(target_asset)
        reducer = _restart_reducer(app_state, reducer, target_asset=target_asset)

    elif action == "pause":
        replay_engine.pause()

    elif action == "resume":
        replay_engine._is_paused = False
        replay_engine._is_running = True

    elif action == "reset":
        replay_engine.reset(clear_time_bounds=(payload.start_time_utc is None and payload.end_time_utc is None))
        app_state.current_state = None
        app_state.latest_fact_bundle = None
        if app_state.feedback_ledger is not None:
            app_state.feedback_ledger.clear(target_asset)
        reducer = _restart_reducer(app_state, reducer, target_asset=target_asset)

    elif action == "seek":
        if payload.seek_position is not None:
            if payload.seek_position < 0 or payload.seek_position > len(replay_engine._events):
                raise ReplayException(
                    message=f"Invalid seek position: {payload.seek_position}",
                    details={"total_events": len(replay_engine._events)},
                )
            target_pos = payload.seek_position
        elif payload.start_time_utc is not None:
            target_pos = replay_engine.seek_time(payload.start_time_utc)
        else:
            raise ReplayException(
                message="Seek action requires either seek_position or start_time_utc.",
            )

        replay_engine.seek(target_pos)
        reducer = _restart_reducer(app_state, reducer)

        if target_pos == 0:
            app_state.current_state = None
            app_state.latest_fact_bundle = None
        else:
            current_state = None
            for ev in replay_engine._events[:target_pos]:
                current_state = reducer.reduce(current_state=current_state, event=ev)
            if current_state is not None:
                manifest = capability_evaluator.evaluate(current_state)
                fact_bundle = assemble_fact_bundle(
                    state=current_state,
                    capability_evaluator=capability_evaluator,
                    capabilities=manifest,
                )
                app_state.update_state(current_state, fact_bundle)

    elif action == "step":
        if not replay_engine._events and storage is not None:
            ensure_dataset_loaded(storage, replay_engine, target_asset)

        stepped_events: list[CanonicalEvent] = []
        for _ in range(payload.batch_size):
            ev = replay_engine.step()
            if ev is None:
                break
            stepped_events.append(ev)

        current_state = app_state.current_state
        for ev in stepped_events:
            current_state = reducer.reduce(current_state=current_state, event=ev)

        if current_state is not None:
            manifest = capability_evaluator.evaluate(current_state)
            fact_bundle = assemble_fact_bundle(
                state=current_state,
                capability_evaluator=capability_evaluator,
                capabilities=manifest,
            )
            app_state.update_state(current_state, fact_bundle)

    return _build_status_response(replay_engine, app_state)
