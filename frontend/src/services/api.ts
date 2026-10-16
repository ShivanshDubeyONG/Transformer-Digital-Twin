/**
 * API Client for Distribution Transformer Digital Twin Backend.
 * Fully typed against backend OpenAPI / v1 contracts.
 */

import {
  AssetStateResponse,
  OTHIBundle,
  AnomalyEpisode,
  MaintenanceRecommendation,
  CapabilityManifest,
  OperatorFeedbackEvent,
  OperatorFeedbackRequest,
  ReplayStatusResponse,
  ReplayControlRequest,
  TelemetryIngestionRequest,
  TelemetryIngestionResponse,
  HistoryResponse,
} from '../types/contracts';

const rawBase = (import.meta.env.VITE_API_BASE as string | undefined)?.trim();
export const API_BASE = rawBase
  ? rawBase.startsWith('http://') || rawBase.startsWith('https://')
    ? rawBase.replace(/\/+$/, '')
    : `https://${rawBase.replace(/\/+$/, '')}`
  : '';

export interface HealthCheckResponse {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  timestamp_utc: string;
  default_asset_id: string;
  is_ready: boolean;
  details?: Record<string, unknown>;
}

export interface ScenarioRequestPayload {
  target_load_u?: number | null;
  load_multiplier?: number;
  target_ambient_degc?: number | null;
  ambient_delta_degc?: number;
  warning_threshold_degc?: number;
  critical_threshold_degc?: number;
  horizon_steps?: number;
}

export interface ScenarioProjectionStepData {
  horizon_step: number;
  horizon_minutes: number;
  projected_time_utc: string;
  projected_top_oil_degc: number;
  projected_rise_over_ambient_degc: number;
  asymptotic_steady_state_degc: number;
  conformal_lower_degc: number;
  conformal_upper_degc: number;
  conformal_half_width_degc: number;
  baseline_top_oil_degc?: number | null;
  scenario_delta_degc?: number | null;
}

export interface ScenarioProjectionResultData {
  asset_id: string;
  origin_time_utc: string;
  origin_top_oil_degc: number;
  origin_ambient_degc: number;
  origin_load_u: number;
  scenario_ambient_degc: number;
  scenario_load_u: number;
  is_enabled: boolean;
  trust_state: string;
  disabled_reason?: string | null;
  is_extrapolated: boolean;
  extrapolation_warning?: string | null;
  trajectory: ScenarioProjectionStepData[];
  peak_projected_top_oil_degc?: number | null;
  asymptotic_steady_state_degc?: number | null;
  earliest_warning_crossing_minutes?: number | null;
  earliest_critical_crossing_minutes?: number | null;
  time_above_warning_minutes?: number | null;
  time_above_critical_minutes?: number | null;
  provenance?: Record<string, unknown>;
}

export interface ModelCardData {
  schema_version: string;
  model_version: string;
  asset_id: string;
  created_at_utc: string;
  selected_load_driver: string;
  load_driver_reference_value: number;
  parameters: {
    beta_0: number;
    beta_1: number;
    tau_hours: number;
  };
  identifiability: {
    is_identifiable: boolean;
    fit_samples_count: number;
    fit_span_days: number;
    load_cv: number;
    diagnostic_messages: string[];
  };
  conformal_uncertainty: {
    horizon_steps: number;
    block_quantile_90: number;
    horizon_half_widths_degc: number[];
  };
  test_metrics: {
    mae_degc: number;
    rmse_degc: number;
    marginal_coverage_90_pct: number;
  };
  promotion: {
    status: string;
    mae_improvement_pct: number;
    all_criteria_met: boolean;
    reasons: string[];
  };
  qualification: Record<string, string>;
}

export interface CpriCapability {
  available: boolean;
  status?: string;
  reason: string;
}

export interface CpriModelEvaluationRow {
  asset_id: string;
  rated_kva: number;
  fit_status: 'FROZEN_CANDIDATE' | 'NOT_FITTED';
  artifact_sha256: string | null;
  promotion_status: string;
  promotion_reasons: string[];
  test_partition: string;
  test_evaluated_at_utc: string | null;
  gates: Record<string, boolean | null> | null;
  metrics: {
    mae_2h_degc: number;
    persistence_mae_2h_degc: number;
    mae_improvement_pct: number;
    signed_bias_degc: number;
    persistence_signed_bias_degc: number;
    marginal_coverage_90_pct: number | null;
    path_coverage_90_pct: number | null;
  } | null;
  capabilities: Record<string, CpriCapability>;
}

export interface CpriModelEvaluation {
  dataset_id: string;
  promotion_policy: Record<string, string>;
  assets: CpriModelEvaluationRow[];
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errJson = await res.json();
      errorDetail = errJson.error?.message || errJson.message || JSON.stringify(errJson);
    } catch {
      // Use statusText
    }
    throw new Error(`API Error (${res.status}): ${errorDetail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // Liveness Probe
  async getHealthz(): Promise<HealthCheckResponse> {
    const res = await fetch(`${API_BASE}/healthz`);
    return handleResponse<HealthCheckResponse>(res);
  },

  // Asset State & FactBundle
  async getAssetState(assetId: string): Promise<AssetStateResponse> {
    const res = await fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}/state`);
    return handleResponse<AssetStateResponse>(res);
  },

  // Multi-Domain Health
  async getAssetHealth(assetId: string): Promise<OTHIBundle> {
    const res = await fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}/health`);
    return handleResponse<OTHIBundle>(res);
  },

  // Anomaly Episodes
  async getAssetEpisodes(
    assetId: string,
    params?: { state?: string; category?: string; limit?: number }
  ): Promise<AnomalyEpisode[]> {
    const searchParams = new URLSearchParams();
    if (params?.state) searchParams.append('state', params.state);
    if (params?.category) searchParams.append('category', params.category);
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const res = await fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}/episodes${query}`);
    return handleResponse<AnomalyEpisode[]>(res);
  },

  // Maintenance Recommendations
  async getAssetRecommendations(
    assetId: string,
    params?: { priority?: string; ruleId?: string }
  ): Promise<MaintenanceRecommendation[]> {
    const searchParams = new URLSearchParams();
    if (params?.priority) searchParams.append('priority', params.priority);
    if (params?.ruleId) searchParams.append('rule_id', params.ruleId);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const res = await fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}/recommendations${query}`);
    return handleResponse<MaintenanceRecommendation[]>(res);
  },

  // Historical Telemetry Events
  async getAssetHistory(
    assetId: string,
    params?: {
      startTime?: string;
      endTime?: string;
      limit?: number;
      offset?: number;
      orderAsc?: boolean;
    }
  ): Promise<HistoryResponse> {
    const searchParams = new URLSearchParams();
    if (params?.startTime) searchParams.append('start_time', params.startTime);
    if (params?.endTime) searchParams.append('end_time', params.endTime);
    if (params?.limit !== undefined) searchParams.append('limit', params.limit.toString());
    if (params?.offset !== undefined) searchParams.append('offset', params.offset.toString());
    if (params?.orderAsc !== undefined) searchParams.append('order_asc', params.orderAsc.toString());
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const res = await fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}/history${query}`);
    return handleResponse<HistoryResponse>(res);
  },

  // Capabilities Manifest
  async getAssetCapabilities(assetId: string): Promise<CapabilityManifest> {
    const res = await fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}/capabilities`);
    return handleResponse<CapabilityManifest>(res);
  },

  // Asset Inventory Catalog
  async getAvailableAssets(): Promise<any> {
    const res = await fetch(`${API_BASE}/v1/assets`);
    return handleResponse<any>(res);
  },

  // Model Card
  async getCpriModelEvaluation(): Promise<CpriModelEvaluation> {
    const res = await fetch(`${API_BASE}/v1/models/cpri-evaluation`);
    return handleResponse<CpriModelEvaluation>(res);
  },

  async getCandidateModelEvaluation(): Promise<CpriModelEvaluation> {
    const res = await fetch(`${API_BASE}/v1/models/candidate-evaluation`);
    return handleResponse<CpriModelEvaluation>(res);
  },

  async getAssetModelCard(assetId: string): Promise<ModelCardData> {
    const res = await fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}/model-card`);
    return handleResponse<ModelCardData>(res);
  },

  // Replay Control & Status
  async getReplayStatus(): Promise<ReplayStatusResponse> {
    const res = await fetch(`${API_BASE}/v1/replay`);
    return handleResponse<ReplayStatusResponse>(res);
  },

  async controlReplay(payload: ReplayControlRequest): Promise<ReplayStatusResponse> {
    const res = await fetch(`${API_BASE}/v1/replay`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<ReplayStatusResponse>(res);
  },

  // Telemetry Ingestion
  async ingestTelemetry(payload: TelemetryIngestionRequest): Promise<TelemetryIngestionResponse> {
    const res = await fetch(`${API_BASE}/v1/telemetry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<TelemetryIngestionResponse>(res);
  },

  // 2-Hour What-If Scenario Simulator
  async runScenario(assetId: string, payload: ScenarioRequestPayload): Promise<ScenarioProjectionResultData> {
    const res = await fetch(`${API_BASE}/v1/assets/${encodeURIComponent(assetId)}/scenario`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<ScenarioProjectionResultData>(res);
  },

  // Submit Operator Feedback
  async submitFeedback(payload: OperatorFeedbackRequest): Promise<OperatorFeedbackEvent> {
    const res = await fetch(`${API_BASE}/v1/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse<OperatorFeedbackEvent>(res);
  },

  // Operator Feedback History
  async getFeedback(params?: {
    assetId?: string;
    recommendationId?: string;
    action?: string;
  }): Promise<OperatorFeedbackEvent[]> {
    const searchParams = new URLSearchParams();
    if (params?.assetId) searchParams.append('asset_id', params.assetId);
    if (params?.recommendationId) searchParams.append('recommendation_id', params.recommendationId);
    if (params?.action) searchParams.append('action', params.action);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const res = await fetch(`${API_BASE}/v1/feedback${query}`);
    return handleResponse<OperatorFeedbackEvent[]>(res);
  },

  // Persisted Checkpoint Runs & Reports
  async createCheckpoint(assetId?: string): Promise<CheckpointRunRecord> {
    const searchParams = new URLSearchParams();
    if (assetId) searchParams.append('asset_id', assetId);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const res = await fetch(`${API_BASE}/v1/reports/checkpoints${query}`, {
      method: 'POST',
    });
    return handleResponse<CheckpointRunRecord>(res);
  },

  async getRuns(assetId?: string, limit?: number): Promise<CheckpointRunRecord[]> {
    const searchParams = new URLSearchParams();
    if (assetId) searchParams.append('asset_id', assetId);
    if (limit !== undefined) searchParams.append('limit', limit.toString());
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    const res = await fetch(`${API_BASE}/v1/reports/runs${query}`);
    return handleResponse<CheckpointRunRecord[]>(res);
  },

  getReportDownloadUrl(format: 'json' | 'csv' | 'pdf', assetId?: string, checkpointId?: string): string {
    const searchParams = new URLSearchParams();
    if (assetId) searchParams.append('asset_id', assetId);
    if (checkpointId) searchParams.append('checkpoint_id', checkpointId);
    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return `${API_BASE}/v1/reports/summary.${format}${query}`;
  },
};

export interface CheckpointRunRecord {
  checkpoint_id: string;
  asset_id: string;
  state_time_utc: string;
  last_processed_event_id?: string;
  state_sequence: number;
  state_hash: string;
  created_at_utc: string;
}

