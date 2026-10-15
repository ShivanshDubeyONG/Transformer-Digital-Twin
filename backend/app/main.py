"""FastAPI Application Entrypoint, Lifecycle Configuration & OpenAPI Integration (Phase 7.4).

POWERNext-AI Hackathon 2026 — Track 2: Digital Twin for Intelligent Health Monitoring
and Predictive Maintenance of Distribution Transformers.

Provides the complete 12 canonical REST API endpoints, CORS middleware, centralized
error handling, and comprehensive OpenAPI documentation with UI-honesty metadata tags:
- DEMO_DEFAULT: Clearly distinguishes demonstration parameters from site-calibrated standards.
- relative_load_index: Transparently reported when nameplate rated kVA is unavailable.
- SYNTHETIC_SCENARIO: Explicitly labels what-if simulations and injected test anomalies.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import AppState, get_app_state
from app.api.errors import register_exception_handlers
from app.api.routers import api_v1_router
from app.api.schemas import HealthCheckResponse
from app.core.config import Settings, get_settings
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.reducer import TwinReducer
from app.engine.replay import ReplayEngine


OPENAPI_TAGS: list[dict[str, Any]] = [
    {
        "name": "Telemetry",
        "description": (
            "Ingestion of raw telemetry frames and canonical telemetry events. "
            "Persists events to DuckDB temporal storage, advances the deterministic state "
            "reducer F(TwinState_{t-1}, Event_t) -> TwinState_t, and updates the active FactBundle. "
            "**[UI-Honesty Notice: `relative_load_index` is reported when rated kVA is absent.]**"
        ),
    },
    {
        "name": "Replay",
        "description": (
            "Deterministic chronological replay control (start, pause, resume, step, reset, seek) "
            "for testing, validation, and demo playback of historical transformer datasets."
        ),
    },
    {
        "name": "Assets",
        "description": (
            "Active digital twin state vector, historical telemetry queries, and dynamic C0–C4 capability tier manifests. "
            "**[UI-Honesty Notice: Missing telemetry gracefully downgrades capability tiers rather than inventing synthetic data.]**"
        ),
    },
    {
        "name": "Analytics & Scenarios",
        "description": (
            "Multi-domain operational health index (gated OTHI across 5 domains), anomaly episodes, "
            "prioritized maintenance recommendations, thermal model card metadata, and bounded 2-hour what-if scenario simulations. "
            "**[UI-Honesty Notice: Demonstration defaults are labeled `DEMO_DEFAULT`. What-if simulations are labeled `SYNTHETIC_SCENARIO`.]**"
        ),
    },
    {
        "name": "Feedback",
        "description": (
            "Append-only immutable audit ledger for human-in-the-loop operator actions (ACKNOWLEDGE, DISMISS, "
            "INSPECTION_OUTCOME, OVERRIDE). Enforces P0 safety resolution rules and preserves historical telemetry."
        ),
    },
    {
        "name": "System",
        "description": "Application liveness probe, subsystem readiness diagnostics, and environment verification.",
    },
]

API_DESCRIPTION = """
## POWERNext-AI Hackathon 2026 — Track 2: Digital Twin for Distribution Transformer Health Monitoring

### System Overview
A stateful, physics-grounded reduced-order digital twin for distribution transformers operating in chronological replay.
Integrates continuous electrical telemetry, a first-order grey-box thermal ODE ($\beta_0, \beta_1, \tau$), empirical 90%
conformal uncertainty bounds, multi-domain health index (gated OTHI), and deterministic maintenance rule policies.

### UI-Honesty and Safety Guarantees
1. **`DEMO_DEFAULT`**: Any default parameters, heuristic action windows, or uncalibrated limits are conspicuously labeled.
2. **`relative_load_index`**: Reported when transformer nameplate rating is unverified, avoiding ungrounded per-unit claims.
3. **`SYNTHETIC_SCENARIO`**: What-if forward projections and injected anomaly scenarios carry explicit synthetic labels.
4. **No Unsupported Claims**: The system does **not** output numeric RUL, probability of failure, or autonomous switching commands.
5. **Immutable Provenance**: Historical telemetry, evidence records, and OTHI evaluations are never overwritten.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager initializing storage, engines, and graceful shutdown."""
    settings = getattr(app.state, "settings", None) or get_settings()
    app_state = getattr(app.state, "app_state", None)

    if app_state is None:
        storage = StorageEngine(db_path=settings.db_path)
        feedback_ledger = OperatorFeedbackLedger()
        from app.api.deps import build_runtime_reducer
        from app.core.registry import resolve_asset_profile, resolve_model_artifact
        profile = resolve_asset_profile(asset_id=settings.default_asset_id)
        artifact = resolve_model_artifact(asset_id=settings.default_asset_id)
        is_promoted = artifact.parameters is not None and artifact.promotion.status == "PROMOTED"
        capability_evaluator = CapabilityEvaluator(
            profile=profile,
            expected_cadence_s=profile.expected_cadence_s,
            evaluation_window_s=settings.evaluation_window_s,
            # C3 forecasting follows the asset's locked qualification matrix; unpromoted assets stay gated
            is_model_promoted=is_promoted,
            qualification=artifact.qualification if is_promoted else None,
            model_version=artifact.model_version if is_promoted else "uncalibrated",
        )

        def reducer_factory(asset_id: str | None = None) -> TwinReducer:
            target = asset_id or (app_state.replay_engine.asset_id if app_state and app_state.replay_engine else settings.default_asset_id)
            return build_runtime_reducer(settings, feedback_ledger, asset_id=target, storage=storage)

        reducer = reducer_factory()
        replay_engine = ReplayEngine(storage=storage, asset_id=settings.default_asset_id)

        app_state = AppState(
            settings=settings,
            storage=storage,
            profile=profile,
            model_artifact=artifact,
            reducer=reducer,
            capability_evaluator=capability_evaluator,
            feedback_ledger=feedback_ledger,
            replay_engine=replay_engine,
            reducer_factory=reducer_factory,
        )
        app.state.app_state = app_state

        if settings.environment != "test":
            from app.api.routers.replay import ensure_dataset_loaded
            ensure_dataset_loaded(storage, replay_engine, settings.default_asset_id)

    yield

    if app_state and app_state.storage:
        app_state.storage.close()


def create_app(
    settings: Settings | None = None,
    app_state: AppState | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application instance with complete OpenAPI metadata."""
    cfg = settings or get_settings()

    app = FastAPI(
        title=cfg.app_name,
        description=API_DESCRIPTION,
        version=cfg.app_version,
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.state.settings = cfg
    if app_state is not None:
        app.state.app_state = app_state

    origins = cfg.cors_origins if cfg.cors_origins else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    # Mount canonical v1 routers
    app.include_router(api_v1_router)

    # Infrastructure Liveness & Readiness Probe
    @app.get(
        "/healthz",
        response_model=HealthCheckResponse,
        status_code=status.HTTP_200_OK,
        tags=["System"],
        summary="Application liveness and subsystem readiness probe",
    )
    async def healthcheck(

        state: AppState = Depends(get_app_state),
    ) -> HealthCheckResponse:
        """Return application health status and runtime subsystem readiness."""
        is_ready = bool(state.storage is not None and state.reducer is not None)
        return HealthCheckResponse(
            status="ok" if is_ready else "degraded",
            app_name=cfg.app_name,
            version=cfg.app_version,
            environment=cfg.environment,
            timestamp_utc=datetime.now(timezone.utc),
            default_asset_id=cfg.default_asset_id,
            is_ready=is_ready,
            details={
                "storage_connected": state.storage is not None,
                "reducer_initialized": state.reducer is not None,
                "capability_evaluator_initialized": state.capability_evaluator is not None,
                "feedback_ledger_initialized": state.feedback_ledger is not None,
                "current_state_present": state.current_state is not None,
            },
        )

    return app


app = create_app()
