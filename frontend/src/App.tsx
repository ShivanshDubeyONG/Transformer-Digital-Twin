import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Navbar } from './components/Navbar';
import { ReplayBar } from './components/layout/ReplayBar';
import { OverviewView } from './components/views/OverviewView';
import { TwinAnalysisView } from './components/views/TwinAnalysisView';
import { AnomalyTimelineView } from './components/views/AnomalyTimelineView';
import { MaintenanceView } from './components/views/MaintenanceView';
import { TelemetryView } from './components/views/TelemetryView';
import { DataModelCardView } from './components/views/DataModelCardView';
import { Transformer3DView } from './components/views/Transformer3DView';
import { HistoricalPerformanceView } from './components/views/HistoricalPerformanceView';
import { FeedbackModal } from './components/FeedbackModal';
import { ModelCardModal } from './components/ModelCardModal';
import { PanelLeftOpen } from 'lucide-react';

import {
  TwinState,
  OTHIBundle,
  MaintenanceRecommendation,
  AnomalyEpisode,
  CapabilityManifest,
  ReplayStatusResponse,
  CanonicalEvent,
  ReviewFlagRecord,
} from './types/contracts';
import { api, ModelCardData } from './services/api';
import { getAssetContext } from './utils/assetContext';
import { ModelEvaluationMatrix } from './components/views/ModelEvaluationMatrix';

export default function App(): React.ReactElement {
  // The backend serves one configured asset (DEFAULT_ASSET_ID); the UI follows it rather than hardcoding one.
  const [assetId, setAssetId] = useState<string>('');
  const selectedDataset = getAssetContext(assetId).datasetId;
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<string>('overview');

  // Desktop sidebar collapse state (persisted to localStorage)
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem('gridpulse_sidebar_open');
      return stored !== null ? stored === 'true' : true;
    } catch {
      return true;
    }
  });

  const handleToggleSidebar = () => {
    setIsSidebarOpen((prev) => {
      const next = !prev;
      try {
        localStorage.setItem('gridpulse_sidebar_open', String(next));
      } catch {
        // ignore
      }
      return next;
    });
  };

  // Digital Twin Lifecycle & Playback State
  const [isTwinStarted, setIsTwinStarted] = useState<boolean>(false);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [replayStatus, setReplayStatus] = useState<ReplayStatusResponse | null>(null);
  const [speedMultiplier, setSpeedMultiplier] = useState<number>(1);
  const isSteppingRef = useRef<boolean>(false);
  const activeAssetIdRef = useRef<string>('');
  const loadReqIdRef = useRef<number>(0);

  // Core Twin State (begins unseeded / ready)
  const [twinState, setTwinState] = useState<TwinState | null>(null);
  const [health, setHealth] = useState<OTHIBundle | null>(null);
  const [recommendations, setRecommendations] = useState<MaintenanceRecommendation[]>([]);
  const [episodes, setEpisodes] = useState<AnomalyEpisode[]>([]);
  const [activeReviews, setActiveReviews] = useState<ReviewFlagRecord[]>([]);
  const [capabilities, setCapabilities] = useState<CapabilityManifest | null>(null);

  const [historyEvents, setHistoryEvents] = useState<CanonicalEvent[]>([]);
  const [healthHistory, setHealthHistory] = useState<Array<{ health: OTHIBundle; recommendations: MaintenanceRecommendation[] }>>([]);
  const [modelCard, setModelCard] = useState<ModelCardData | null>(null);
  const [resetCount, setResetCount] = useState<number>(0);

  // Dark mode state with persistence
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    return (localStorage.getItem('gridpulse_theme') as 'light' | 'dark') || 'light';
  });

  useEffect(() => {
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('gridpulse_theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'light' ? 'dark' : 'light'));
  };

  // UI States
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isSeeding, setIsSeeding] = useState<boolean>(false);
  const [selectedRecForFeedback, setSelectedRecForFeedback] =
    useState<MaintenanceRecommendation | null>(null);
  const [isModelCardOpen, setIsModelCardOpen] = useState<boolean>(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  // 1. Fetch Backend Health, Asset State/FactBundle, History, and Model-Card
  const applyAssetState = useCallback((data: any, status?: ReplayStatusResponse | null) => {
    if (status) {
      setReplayStatus(status);
      if (status.processed_events > 0) {
        setIsTwinStarted(true);
      }
    }
    setTwinState(data.twin_state ?? null);
    if (data.fact_bundle) {
      const currentHealth = data.fact_bundle.health ?? null;
      const recs = data.fact_bundle.active_recommendations ?? [];
      setHealth(currentHealth);
      setRecommendations(recs);
      setEpisodes(data.fact_bundle.open_episodes ?? []);
      setActiveReviews(data.fact_bundle.active_reviews ?? data.twin_state?.active_reviews ?? []);
      if (data.fact_bundle.capabilities) {
        setCapabilities(data.fact_bundle.capabilities);
      }
      if (currentHealth && typeof currentHealth.othi_score === 'number') {
        setHealthHistory((prev) => {
          if (
            prev.length > 0 &&
            prev[prev.length - 1].health.timestamp_utc === currentHealth.timestamp_utc &&
            prev[prev.length - 1].health.othi_score === currentHealth.othi_score
          ) {
            return prev;
          }
          return [...prev, { health: currentHealth, recommendations: recs }];
        });
      }
    } else {
      setHealth(null);
      setRecommendations([]);
      setEpisodes([]);
      setActiveReviews(data.twin_state?.active_reviews ?? []);
      setCapabilities(null);
    }
  }, []);

  const loadState = useCallback(async (currentAssetId: string, overrideStatus?: ReplayStatusResponse | null) => {
    if (!currentAssetId) return;
    const reqId = ++loadReqIdRef.current;
    setIsRefreshing(true);
    try {
      const [healthRes, stateRes, modelCardRes, replayStatusRes] = await Promise.allSettled([
        api.getHealthz(),
        api.getAssetState(currentAssetId),
        api.getAssetModelCard(currentAssetId),
        api.getReplayStatus(),
      ]);

      if (reqId !== loadReqIdRef.current || currentAssetId !== activeAssetIdRef.current) {
        return;
      }

      // 1. Process Health
      if (healthRes.status === 'fulfilled') {
        setIsBackendHealthy(healthRes.value.is_ready);
      } else {
        setIsBackendHealthy(false);
      }

      // 2. Sync Replay Status
      let effectiveStatus = overrideStatus !== undefined ? overrideStatus : null;
      if (replayStatusRes.status === 'fulfilled' && replayStatusRes.value) {
        effectiveStatus = overrideStatus !== undefined ? overrideStatus : replayStatusRes.value;
        setReplayStatus(effectiveStatus);
        if (effectiveStatus && effectiveStatus.processed_events > 0) {
          setIsTwinStarted(true);
        }
      }

      // 3. Process Asset State & FactBundle
      let currentWatermark: string | null = null;
      if (stateRes.status === 'fulfilled' && stateRes.value) {
        applyAssetState(stateRes.value, effectiveStatus);
        currentWatermark = stateRes.value.twin_state?.event_time_watermark_utc || stateRes.value.twin_state?.state_time_utc || null;
      } else {
        setTwinState(null);
        setHealth(null);
        setRecommendations([]);
        setEpisodes([]);
        setCapabilities(null);
      }

      // 4. Process History Events (Rolling latest 50 events up to current watermark)
      const hasProcessedFrames = (effectiveStatus?.processed_events ?? 0) > 0;
      const queryEndTime = currentWatermark || effectiveStatus?.current_time_utc || null;

      if (hasProcessedFrames && queryEndTime) {
        try {
          const historyRes = await api.getAssetHistory(currentAssetId, {
            endTime: queryEndTime,
            limit: 50,
            orderAsc: false,
          });
          if (historyRes?.events) {
            const chronoSorted = [...historyRes.events].sort(
              (a, b) => new Date(a.event_time_utc).getTime() - new Date(b.event_time_utc).getTime()
            );
            setHistoryEvents(chronoSorted);
          }
        } catch {
          // Preserve current buffer on transient history query failure
        }
      } else {
        setHistoryEvents([]);
      }

      // 5. Process Calibrated Model Card
      if (modelCardRes.status === 'fulfilled' && modelCardRes.value) {
        setModelCard(modelCardRes.value);
      }
    } finally {
      setIsRefreshing(false);
    }
  }, [applyAssetState]);

  useEffect(() => {
    api
      .getHealthz()
      .then((h) => setAssetId(h.default_asset_id))
      .catch(() => setIsBackendHealthy(false));
  }, []);

  useEffect(() => {
    if (!assetId) return;
    activeAssetIdRef.current = assetId;
    loadState(assetId);
  }, [assetId, loadState]);

  // Advance one frame or batch and update dynamic state swiftly
  const stepFrame = useCallback(async (batchSize: number = 1) => {
    if (isSteppingRef.current) return;
    isSteppingRef.current = true;
    try {
      const res = await api.controlReplay({
        action: 'step',
        batch_size: batchSize,
        asset_id: assetId,
        speed_multiplier: speedMultiplier,
      });
      setReplayStatus(res);
      if (res.is_completed && res.total_events > 0) {
        setIsPlaying(false);
        showToast('Dataset replay completed.');
      }
      const stateData = await api.getAssetState(assetId);
      applyAssetState(stateData, res);

      const wm = stateData.twin_state?.event_time_watermark_utc || res.current_time_utc;
      if (wm && (res.processed_events % 2 === 0 || batchSize > 1)) {
        api.getAssetHistory(assetId, { endTime: wm, limit: 50, orderAsc: false }).then((h) => {
          if (h?.events) {
            const chronoSorted = [...h.events].sort(
              (a, b) => new Date(a.event_time_utc).getTime() - new Date(b.event_time_utc).getTime()
            );
            setHistoryEvents(chronoSorted);
          }
        }).catch(() => {});
      }
    } catch (err: unknown) {
      setIsPlaying(false);
      const msg = err instanceof Error ? err.message : 'Replay step failed';
      showToast(msg);
    } finally {
      isSteppingRef.current = false;
    }
  }, [assetId, speedMultiplier, applyAssetState]);

  // 2. Start Digital Twin Action
  const handleStartTwin = async () => {
    try {
      const res = await api.controlReplay({
        action: 'start',
        asset_id: assetId,
        speed_multiplier: speedMultiplier,
      });
      setReplayStatus(res);
      setIsTwinStarted(true);
      setIsPlaying(false);
      await loadState(assetId, res);
      showToast('Digital Twin initialized. Ready for telemetry replay.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start Digital Twin';
      showToast(msg);
    }
  };

  // 3. Manual Next-Frame Telemetry Stepper (1 frame or batch)
  const handleNext = async (batchSize: number = 1) => {
    await stepFrame(batchSize);
  };

  // 4. Play / Pause Automatic Replay
  const handlePlayToggle = async () => {
    if (!isTwinStarted) {
      try {
        const startRes = await api.controlReplay({
          action: 'start',
          asset_id: assetId,
          speed_multiplier: speedMultiplier,
        });
        setReplayStatus(startRes);
        setIsTwinStarted(true);
        setIsPlaying(true);
        showToast('Digital Twin started. Playing telemetry stream.');
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to start Digital Twin';
        showToast(msg);
      }
      return;
    }

    if (isPlaying) {
      setIsPlaying(false);
      try {
        const res = await api.controlReplay({
          action: 'pause',
          asset_id: assetId,
        });
        setReplayStatus(res);
      } catch {
        // ignore
      }
    } else {
      setIsPlaying(true);
      try {
        const res = await api.controlReplay({
          action: 'resume',
          asset_id: assetId,
          speed_multiplier: speedMultiplier,
        });
        setReplayStatus(res);
      } catch {
        // ignore
      }
    }
  };

  // 5. Automatic Playback Loop
  useEffect(() => {
    if (!isPlaying) return;

    const delayMs = speedMultiplier === 10 ? 150 : speedMultiplier === 5 ? 350 : 1200;
    const interval = setInterval(() => {
      stepFrame(1);
    }, delayMs);

    return () => clearInterval(interval);
  }, [isPlaying, speedMultiplier, stepFrame]);

  // 6. Speed Multiplier Change
  const handleSpeedChange = async (speed: number) => {
    setSpeedMultiplier(speed);
    if (isPlaying) {
      try {
        const res = await api.controlReplay({
          action: 'resume',
          speed_multiplier: speed,
          asset_id: assetId,
        });
        setReplayStatus(res);
      } catch {
        // ignore
      }
    }
  };

  // 6.5. Previous Telemetry Frame Navigation
  const handlePrevious = async () => {
    if (isSteppingRef.current || !isTwinStarted) return;
    const currentCursor = replayStatus?.processed_events ?? 0;
    if (currentCursor <= 0) return;
    isSteppingRef.current = true;
    try {
      const targetPos = Math.max(0, currentCursor - 1);
      const res = await api.controlReplay({
        action: 'seek',
        seek_position: targetPos,
        asset_id: assetId,
      });
      setReplayStatus(res);
      const stateData = await api.getAssetState(assetId);
      applyAssetState(stateData, res);
      const wm = stateData.twin_state?.event_time_watermark_utc || res.current_time_utc;
      if (wm) {
        api.getAssetHistory(assetId, { endTime: wm, limit: 50, orderAsc: false }).then((h) => {
          if (h?.events) {
            const chronoSorted = [...h.events].sort(
              (a, b) => new Date(a.event_time_utc).getTime() - new Date(b.event_time_utc).getTime()
            );
            setHistoryEvents(chronoSorted);
          }
        }).catch(() => {});
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Previous step failed';
      showToast(msg);
    } finally {
      isSteppingRef.current = false;
    }
  };

  // 7. Reset Replay to Initial State
  const handleReset = async () => {
    setIsPlaying(false);
    setIsTwinStarted(false);
    setResetCount((c) => c + 1);
    setTwinState(null);
    setHealth(null);
    setRecommendations([]);
    setEpisodes([]);
    setActiveReviews([]);
    setCapabilities(null);
    setHistoryEvents([]);
    setHealthHistory([]);
    try {
      const res = await api.controlReplay({
        action: 'reset',
        asset_id: assetId,
      });
      setReplayStatus(res);
      await loadState(assetId, res);
      showToast('Digital Twin reset to initial state.');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Reset failed';
      showToast(msg);
    }
  };

  // 7.5. Switch Asset with Complete State Isolation
  const handleAssetChange = async (newAssetId: string) => {
    if (newAssetId === assetId) return;
    activeAssetIdRef.current = newAssetId;
    setIsPlaying(false);
    setIsTwinStarted(false);
    setTwinState(null);
    setHealth(null);
    setRecommendations([]);
    setEpisodes([]);
    setActiveReviews([]);
    setCapabilities(null);
    setHistoryEvents([]);
    setHealthHistory([]);
    setModelCard(null);
    setAssetId(newAssetId);
    try {
      const res = await api.controlReplay({
        action: 'reset',
        asset_id: newAssetId,
      });
      setReplayStatus(res);
      await loadState(newAssetId, res);
      showToast(`Switched to transformer ${newAssetId}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Asset switch failed';
      showToast(msg);
    }
  };

  const handleDatasetChange = async (newDatasetId: string) => {
    if (newDatasetId === selectedDataset) return;
    const targetAsset = newDatasetId === 'gridpulse_synthetic_v1' ? 'DT-01' : 'TX_1000_COMM';
    await handleAssetChange(targetAsset);
    const label =
      newDatasetId === 'gridpulse_synthetic_v1'
        ? 'GridPulse Synthetic v1.0.0 (Candidate)'
        : 'CPRI Synthetic Benchmark v3.0.2 (Baseline)';
    showToast(`Switched dataset to ${label}`);
  };

  // 8. Seed Trip Fault Fixture (for discrete protection trip demo)
  const handleSeedTripData = async () => {
    // The trip must be stamped on the replay timeline. A wall-clock timestamp would push the twin
    // watermark past every remaining replay frame and freeze OTHI at 0, so require a running twin.
    const wm = twinState?.event_time_watermark_utc;
    if (!wm || !(new Date(wm).getTime() > 0)) {
      showToast('Start the replay and step at least one frame before injecting a protection trip.');
      return;
    }
    setIsSeeding(true);
    try {
      const assetCtx = getAssetContext(assetId);
      const cadenceMs = (assetCtx.cadenceSeconds || 1800) * 1000;
      const eventTime = new Date(new Date(wm).getTime() + cadenceMs).toISOString();

      const tripEvent = {
        schema_version: '1.0.0',
        event_id: `evt-trip-${Date.now()}`,
        asset_id: assetId,
        event_time_utc: eventTime,
        source: {
          system: 'protection_relay_trip',
          adapter_id: 'trip_adapter',
          source_record_id: 'rec_trip',
          source_uri: 'fixtures/fixture_direct_protection_trip.json',
          raw_sha256: '4444555566667777888899990000111122223333444455556666777788889999',
        },
        measurements: [
          {
            signal_id: 'oil_temp_trip_flag',
            value: true,
            value_type: 'bool' as const,
            unit_ucum: '1',
            original_name: 'OTI_T',
            original_value: '1',
            original_unit: 'flag',
            quality: { severity: 'BAD' as const, flags: ['DIRECT_TRIP'] },
          },
          {
            signal_id: 'top_oil_temperature',
            value: 98.4,
            value_type: 'float' as const,
            unit_ucum: 'Cel',
            original_name: 'OTI',
            original_value: '98.4',
            original_unit: 'degC',
            quality: { severity: 'BAD' as const, flags: ['CRITICAL_LIMIT'] },
          },
          {
            signal_id: 'current_i1',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'A',
            original_name: 'I_R',
            original_value: '0.0',
            original_unit: 'A',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'current_i2',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'A',
            original_name: 'I_Y',
            original_value: '0.0',
            original_unit: 'A',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'current_i3',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'A',
            original_name: 'I_B',
            original_value: '0.0',
            original_unit: 'A',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'current_l1',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'A',
            original_name: 'I_R',
            original_value: '0.0',
            original_unit: 'A',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'current_l2',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'A',
            original_name: 'I_Y',
            original_value: '0.0',
            original_unit: 'A',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'current_l3',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'A',
            original_name: 'I_B',
            original_value: '0.0',
            original_unit: 'A',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'active_power_total',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'kW',
            original_name: 'P',
            original_value: '0.0',
            original_unit: 'kW',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'reactive_power_total',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'kvar',
            original_name: 'Q',
            original_value: '0.0',
            original_unit: 'kvar',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'apparent_power_total',
            value: 0.0,
            value_type: 'float' as const,
            unit_ucum: 'kVA',
            original_name: 'S',
            original_value: '0.0',
            original_unit: 'kVA',
            quality: { severity: 'GOOD' as const, flags: [] },
          },
          {
            signal_id: 'lv_breaker_closed',
            value: false,
            value_type: 'bool' as const,
            unit_ucum: '1',
            original_name: '52A_STATUS',
            original_value: '0',
            original_unit: 'binary',
            quality: { severity: 'GOOD' as const, flags: ['BREAKER_TRIPPED'] },
          },
        ],
        event_quality_flags: ['PROTECTION_TRIP_ACTIVE'],
        mapping_version: '1.0.0',
      };

      await api.ingestTelemetry({
        asset_id: assetId,
        events: [tripEvent],
      });

      showToast('Protection Trip Injected: Breaker opened (current = 0 A), OTI_T latched (OTHI = 0 / CRITICAL). Operator clearance required.');
      await loadState(assetId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Trip injection failed';
      showToast(msg);
    } finally {
      setIsSeeding(false);
    }
  };

  // 9. Feedback handler
  const handleFeedbackSuccess = (recId: string, actionChosen: string) => {
    setRecommendations((prev) =>
      prev.map((r) =>
        r.recommendation_id === recId
          ? {
              ...r,
              acknowledged: actionChosen === 'ACKNOWLEDGE',
              acknowledged_at_utc: new Date().toISOString(),
              acknowledged_by: 'OP-SHIVANSH-01',
            }
          : r
      )
    );
    loadState(assetId);
    showToast(`Recommendation ${actionChosen} committed to immutable audit ledger.`);
  };

  const handleQuickAcknowledgeRec = async (rec: MaintenanceRecommendation) => {
    try {
      await api.submitFeedback({
        asset_id: assetId,
        recommendation_id: rec.recommendation_id,
        merge_key: rec.merge_key,
        action: 'ACKNOWLEDGE',
        operator_id: 'OP-SHIVANSH-01',
        notes: 'Operator acknowledged advisory.',
        rationale: 'Operator acknowledged advisory.',
      });
      handleFeedbackSuccess(rec.recommendation_id, 'ACKNOWLEDGE');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Acknowledge failed';
      showToast(msg);
    }
  };

  const handleAcknowledgeReview = async (review: ReviewFlagRecord) => {
    setActiveReviews((prev) =>
      prev.map((r) =>
        r.review_id === review.review_id
          ? { ...r, workflow_state: 'ACKNOWLEDGED', revision: r.revision + 1 }
          : r
      )
    );
    setTwinState((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        active_reviews: (prev.active_reviews || []).map((r) =>
          r.review_id === review.review_id
            ? { ...r, workflow_state: 'ACKNOWLEDGED', revision: r.revision + 1 }
            : r
        ),
      };
    });
    try {
      await api.submitFeedback({
        asset_id: assetId,
        action: 'ACKNOWLEDGE',
        operator_id: 'OP-SHIVANSH-01',
        review_id: review.review_id,
        expected_revision: review.revision,
        rationale: 'Acknowledged review flag by control engineer',
      });
      showToast(`Acknowledged review flag: ${review.condition_family}`);
      await loadState(assetId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Acknowledge failed';
      showToast(msg);
      await loadState(assetId);
    }
  };

  const handleDismissReview = async (review: ReviewFlagRecord) => {
    setActiveReviews((prev) =>
      prev.map((r) =>
        r.review_id === review.review_id
          ? { ...r, workflow_state: 'DISMISSED', revision: r.revision + 1 }
          : r
      )
    );
    setTwinState((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        active_reviews: (prev.active_reviews || []).map((r) =>
          r.review_id === review.review_id
            ? { ...r, workflow_state: 'DISMISSED', revision: r.revision + 1 }
            : r
        ),
      };
    });
    try {
      await api.submitFeedback({
        asset_id: assetId,
        action: 'DISMISS',
        operator_id: 'OP-SHIVANSH-01',
        review_id: review.review_id,
        expected_revision: review.revision,
        rationale: 'Dismissed following operating evaluation',
      });
      showToast(`Dismissed review flag: ${review.condition_family}`);
      await loadState(assetId);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Dismiss failed';
      showToast(msg);
      await loadState(assetId);
    }
  };

  return (
    <div className="min-h-screen text-ink bg-canvas transition-colors">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 max-w-sm bg-inverse text-on-inverse px-4 py-3 rounded-card shadow-elevated text-xs font-medium flex items-center gap-2.5">
          <span className="dot w-2 h-2 bg-accent"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Floating Reopen Sidebar Button for desktop when collapsed */}
      {!isSidebarOpen && (
        <button
          onClick={handleToggleSidebar}
          title="Open navigation sidebar"
          id="btn-open-sidebar"
          className="hidden lg:flex fixed top-3 left-3 z-50 h-8 px-2.5 rounded-lg bg-surface/95 backdrop-blur border border-line shadow-md items-center gap-2 text-ink hover:text-accent hover:border-accent/40 transition-all font-medium text-[12px] group"
        >
          <PanelLeftOpen className="w-4 h-4 text-accent group-hover:scale-105 transition-transform" />
          <span>Open Sidebar</span>
        </button>
      )}

      {/* Top Application Navbar */}
      <Navbar
        isBackendHealthy={isBackendHealthy}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        onRefresh={() => loadState(assetId)}
        isRefreshing={isRefreshing}
        theme={theme}
        onToggleTheme={toggleTheme}
        siteLabel={getAssetContext(assetId).siteLabel}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={handleToggleSidebar}
      />

      <div className={`${isSidebarOpen ? 'lg:pl-60' : 'lg:pl-0'} min-h-screen flex flex-col transition-[padding] duration-300 ease-in-out`}>
      {/* Main Container */}
      <main className={`${activeTab === 'twin-3d' ? 'max-w-[1380px]' : 'max-w-[1320px]'} mx-auto px-4 sm:px-6 lg:px-8 w-full flex-grow pt-4 lg:pt-6 pb-12 transition-all duration-200`}>
        {/* Simplified Digital Twin Workflow & Replay Bar */}
        <ReplayBar
          selectedDataset={selectedDataset}
          onDatasetChange={handleDatasetChange}
          assetId={assetId}
          onAssetChange={handleAssetChange}
          isTwinStarted={isTwinStarted}
          onStartTwin={handleStartTwin}
          replayStatus={replayStatus}
          isPlaying={isPlaying}
          onPlayToggle={handlePlayToggle}
          onNext={handleNext}
          onPrevious={handlePrevious}
          speedMultiplier={speedMultiplier}
          onSpeedChange={handleSpeedChange}
          onReset={handleReset}
          isBackendHealthy={isBackendHealthy}
          isSidebarOpen={isSidebarOpen}
          onToggleSidebar={handleToggleSidebar}
        />

        {/* View 1: Overview */}
        {activeTab === 'overview' && (
          <OverviewView
            assetId={assetId}
            twinState={twinState}
            health={health}
            capabilities={capabilities}
            recommendations={recommendations}
            episodes={episodes}
            historyEvents={historyEvents}
            modelCard={modelCard}
            onNavigateTab={setActiveTab}
            onOpenFeedback={(rec) => setSelectedRecForFeedback(rec)}
            onQuickAcknowledge={handleQuickAcknowledgeRec}
          />
        )}

        {/* View 2: Twin Analysis & What-If */}
        {activeTab === 'twin-analysis' && (
          <TwinAnalysisView
            assetId={assetId}
            twinState={twinState}
            health={health}
            resetKey={resetCount}
            onOpenModelCard={() => setIsModelCardOpen(true)}
          />
        )}

        {/* View 3: Anomaly Timeline */}
        {activeTab === 'anomalies' && (
          <AnomalyTimelineView
            assetId={assetId}
            episodes={episodes}
            twinState={twinState}
            onSeedTripData={handleSeedTripData}
            isSeeding={isSeeding}
          />
        )}

        {/* View 4: Maintenance Advisories */}
        {activeTab === 'maintenance' && (
          <MaintenanceView
            assetId={assetId}
            recommendations={recommendations}
            episodes={episodes}
            activeReviews={activeReviews}
            healthHistory={healthHistory}
            onOpenFeedback={(rec) => setSelectedRecForFeedback(rec)}
            onQuickAcknowledge={handleQuickAcknowledgeRec}
            onAcknowledgeReview={handleAcknowledgeReview}
            onDismissReview={handleDismissReview}
          />
        )}

        {/* View 5: Telemetry & Capabilities */}
        {activeTab === 'telemetry' && (
          <TelemetryView
            assetId={assetId}
            twinState={twinState}
            capabilities={capabilities}
            historyEvents={historyEvents}
          />
        )}

        {/* View 6: Historical Performance & Run Reports */}
        {activeTab === 'historical' && (
          <HistoricalPerformanceView
            assetId={assetId}
            replayStatus={replayStatus}
            twinState={twinState}
          />
        )}

        {/* View 7: Data & Model Card */}
        {activeTab === 'model-card' && (
          <>
            <DataModelCardView modelCard={modelCard} />
            <ModelEvaluationMatrix currentAssetId={assetId} />
          </>
        )}

        {/* View 7: 3D Twin Workspace */}
        {activeTab === 'twin-3d' && (
          <Transformer3DView
            twinState={twinState}
            health={health}
            onNavigateTab={(tab) => setActiveTab(tab as any)}
          />
        )}
      </main>

      {/* Industrial Footer */}
      <footer className="border-t border-line py-5 text-xs text-muted">
        <div className="max-w-[1320px] mx-auto px-4 sm:px-6 lg:px-10 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-ink">
              GridPulse
            </span>
            <span>· Distribution Transformer Digital Twin · POWERNext-AI Hackathon 2026 (Track 2)</span>
          </div>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-mono text-muted">
            <span>{assetId}</span>
            <span>·</span>
            <span>Multi-Domain OTHI</span>
            <span>·</span>
            <span>Conformal Bounds (90%)</span>
          </div>
        </div>
      </footer>
      </div>

      {/* Operator Feedback Modal */}
      <FeedbackModal
        isOpen={Boolean(selectedRecForFeedback)}
        recommendation={selectedRecForFeedback}
        assetId={assetId}
        onClose={() => setSelectedRecForFeedback(null)}
        onSuccess={handleFeedbackSuccess}
      />

      {/* Calibrated Model Card Modal */}
      <ModelCardModal
        isOpen={isModelCardOpen}
        onClose={() => setIsModelCardOpen(false)}
        modelCard={modelCard}
      />
    </div>
  );
}
