import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  AlertTriangle,
  ShieldAlert,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  RefreshCw,
  Layers,
  AlertCircle,
  FileQuestion,
} from 'lucide-react';

import { AnomalyEpisode, TwinState } from '../../types/contracts';
import { api } from '../../services/api';
import { getAssetContext } from '../../utils/assetContext';

interface AnomalyTimelineViewProps {
  assetId?: string;
  episodes: AnomalyEpisode[];
  twinState: TwinState | null;
  onSeedTripData: () => void;
  isSeeding: boolean;
}

export const AnomalyTimelineView: React.FC<AnomalyTimelineViewProps> = ({
  assetId: propAssetId,
  episodes: propEpisodes,
  twinState,
  onSeedTripData,
  isSeeding,
}) => {
  const assetId = propAssetId || twinState?.asset_id || '';
  const [showDetectorMath, setShowDetectorMath] = useState<boolean>(false);
  const isCusumQualified = getAssetContext(assetId).promotionStatus === 'PROMOTED';

  // Continuous streaming episode store across replay (prevents inefficient 500ms HTTP polling)
  const [streamedEpisodesMap, setStreamedEpisodesMap] = useState<Map<string, AnomalyEpisode>>(new Map());
  const [remoteEpisodes, setRemoteEpisodes] = useState<AnomalyEpisode[] | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isMalformed, setIsMalformed] = useState<boolean>(false);

  // Filter state
  const [stateFilter, setStateFilter] = useState<string>('ALL');
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  const fetchEpisodes = useCallback(async () => {
    if (!assetId) return;
    setIsLoading(true);
    setFetchError(null);
    setIsMalformed(false);
    try {
      const res = await api.getAssetEpisodes(assetId);
      if (!Array.isArray(res)) {
        setIsMalformed(true);
        setRemoteEpisodes([]);
      } else {
        setRemoteEpisodes(res);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Network error fetching episodes';
      setFetchError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [assetId]);

  // Initial load only when assetId changes (or manual sync) — NOT on every single replay frame tick!
  useEffect(() => {
    setStreamedEpisodesMap(new Map());
    setRemoteEpisodes(null);
    fetchEpisodes();
  }, [assetId, fetchEpisodes]);

  // Continuous accumulation: stream live episode states from twinState / FactBundle with zero network overhead
  useEffect(() => {
    const liveItems = (propEpisodes && propEpisodes.length > 0)
      ? propEpisodes
      : (twinState?.open_episodes && twinState.open_episodes.length > 0)
        ? twinState.open_episodes
        : null;

    if (!liveItems || liveItems.length === 0) return;

    setStreamedEpisodesMap((prev) => {
      let changed = false;
      const next = new Map(prev);
      for (const ep of liveItems) {
        if (!ep || !ep.episode_id) continue;
        const existing = next.get(ep.episode_id);
        if (
          !existing ||
          existing.state !== ep.state ||
          existing.last_seen_time_utc !== ep.last_seen_time_utc ||
          existing.severity_score !== ep.severity_score ||
          existing.evidence_ids?.length !== ep.evidence_ids?.length
        ) {
          next.set(ep.episode_id, { ...(existing || {}), ...ep });
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [propEpisodes, twinState?.open_episodes]);

  // Merge remote stored episodes with continuously streamed live episodes
  const allEpisodes = useMemo(() => {
    const map = new Map<string, AnomalyEpisode>();
    // 1. Initial / remote episodes from backend
    if (remoteEpisodes && Array.isArray(remoteEpisodes)) {
      for (const ep of remoteEpisodes) {
        if (ep && ep.episode_id) map.set(ep.episode_id, ep);
      }
    }
    // 2. Continuously accumulated live episodes from replay
    for (const [id, ep] of streamedEpisodesMap.entries()) {
      map.set(id, ep);
    }
    // 3. Props episodes (current point in time)
    if (propEpisodes && Array.isArray(propEpisodes)) {
      for (const ep of propEpisodes) {
        if (ep && ep.episode_id) map.set(ep.episode_id, ep);
      }
    }
    const list = Array.from(map.values());
    // Chronological sort: most recent last_seen or start_time first
    return list.sort((a, b) => {
      const timeA = new Date(a.last_seen_time_utc || a.start_time_utc || 0).getTime();
      const timeB = new Date(b.last_seen_time_utc || b.start_time_utc || 0).getTime();
      return timeB - timeA;
    });
  }, [remoteEpisodes, streamedEpisodesMap, propEpisodes]);

  // Derived counts across all episodes
  const critCount = allEpisodes.filter((e) => String(e.state).toUpperCase() === 'CRITICAL').length;
  const warnCount = allEpisodes.filter((e) => String(e.state).toUpperCase() === 'WARNING').length;
  const watchCount = allEpisodes.filter((e) => String(e.state).toUpperCase() === 'WATCH').length;
  const closedCount = allEpisodes.filter((e) => String(e.state).toUpperCase() === 'CLOSED').length;

  // Available categories for filtering
  const availableCategories = useMemo(() => {
    const set = new Set<string>();
    for (const ep of allEpisodes) {
      if (ep.category) set.add(ep.category);
    }
    return Array.from(set);
  }, [allEpisodes]);

  // Filtered display list
  const filteredEpisodes = useMemo(() => {
    return allEpisodes.filter((ep) => {
      const epState = String(ep.state).toUpperCase();
      if (stateFilter !== 'ALL') {
        if (stateFilter === 'ACTIVE' && epState === 'CLOSED') return false;
        if (stateFilter !== 'ACTIVE' && epState !== stateFilter) return false;
      }
      if (categoryFilter !== 'ALL' && ep.category !== categoryFilter) {
        return false;
      }
      return true;
    });
  }, [allEpisodes, stateFilter, categoryFilter]);

  const formatUtcTime = (isoString?: string) => {
    if (!isoString) return '—';
    try {
      return new Date(isoString).toISOString().replace('T', ' ').slice(0, 19) + ' UTC';
    } catch {
      return isoString;
    }
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="eyebrow">Diagnostic Evidence</span>
            <span className="text-faint">·</span>
            <span className="eyebrow">8 Anomaly Detector Families</span>
            <span className="text-faint">·</span>
            <span className="chip chip-ok text-[10.5px] font-medium flex items-center gap-1.5 py-0.5">
              <span className="dot w-1.5 h-1.5 bg-ok animate-pulse" />
              Continuous Live Stream
            </span>
          </div>
          <h1 className="page-title">Anomalies &amp; Evidence</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Multi-domain anomaly detection tracking statistical rate-of-change, thermal residual drift, and discrete protection trips.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={fetchEpisodes}
            disabled={isLoading}
            className="btn btn-ghost"
            title="Manual sync from backend episode database"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-accent' : ''}`} />
            <span>{isLoading ? 'Syncing...' : 'Sync Episodes'}</span>
          </button>
          <button
            onClick={onSeedTripData}
            disabled={isSeeding}
            className="btn btn-danger self-start lg:self-auto"
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>{isSeeding ? 'Injecting...' : 'Inject Protection Trip Fixture'}</span>
          </button>
        </div>
      </div>

      {/* Episode Summary Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-line border border-line rounded-card overflow-hidden">
        {[
          { label: 'Total Tracked', value: allEpisodes.length, dot: 'bg-faint', sub: 'Historical & active' },
          { label: 'Critical Incidents', value: critCount, dot: critCount > 0 ? 'bg-crit animate-pulse' : 'bg-line-strong', sub: 'P0 escalation' },
          { label: 'Warning Level', value: warnCount, dot: warnCount > 0 ? 'bg-warn' : 'bg-line-strong', sub: 'Requires inspection' },
          { label: 'Watch / Closed', value: `${watchCount} / ${closedCount}`, dot: 'bg-line-strong', sub: 'Normalizing / resolved' },
        ].map((s) => (
          <div key={s.label} className="bg-surface p-5">
            <div className="flex items-center justify-between pb-3 border-b border-line">
              <span className="eyebrow text-[11px]">{s.label}</span>
              <span className={`dot w-2 h-2 ${s.dot}`} />
            </div>
            <div className="metric-value text-[32px] sm:text-[38px] mt-3 font-mono">{s.value}</div>
            <span className="text-[11px] text-muted mt-1 block">{s.sub}</span>
          </div>
        ))}
      </div>

      {/* Active & Tracked Episodes Event Ledger */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-3 mb-4">
          <div>
            <h2 className="section-title">
              Anomaly Episodes Log ({filteredEpisodes.length} of {allEpisodes.length})
            </h2>
            <span className="text-[11px] text-muted font-mono block mt-0.5">
              Finite State Machine: OPEN → CORROBORATED → RESOLVED / CLOSED
            </span>
          </div>

          {/* Filtering Controls */}
          {allEpisodes.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <div className="segmented text-[11px]">
                {['ALL', 'ACTIVE', 'CRITICAL', 'WARNING', 'CLOSED'].map((sf) => (
                  <button
                    key={sf}
                    onClick={() => setStateFilter(sf)}
                    data-active={stateFilter === sf}
                    className="py-1 px-2.5 font-medium"
                  >
                    {sf === 'ALL' ? 'All States' : sf}
                  </button>
                ))}
              </div>

              {availableCategories.length > 1 && (
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="input text-xs py-1 px-2 font-medium"
                >
                  <option value="ALL">All Categories</option>
                  {availableCategories.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </select>
              )}
            </div>
          )}
        </div>

        {/* State 1: Loading in progress */}
        {isLoading && allEpisodes.length === 0 && (
          <div className="card p-12 text-center text-xs text-muted">
            <RefreshCw className="w-6 h-6 mx-auto animate-spin text-accent mb-3" />
            <p className="card-title">Querying anomaly episodes...</p>
            <p className="text-[11px] text-muted mt-1">
              Checking diagnostic episode store for asset <span className="font-mono text-ink">{assetId}</span>.
            </p>
          </div>
        )}

        {/* State 2: Network / API Failure */}
        {fetchError && allEpisodes.length === 0 && (
          <div className="card p-8 border-crit/30 bg-crit/5 text-center">
            <AlertCircle className="w-7 h-7 mx-auto text-crit mb-3" />
            <p className="text-sm font-semibold text-crit">Failed to Retrieve Anomaly Episodes</p>
            <p className="text-xs text-muted max-w-md mx-auto mt-1 mb-4">{fetchError}</p>
            <button onClick={fetchEpisodes} className="btn btn-secondary text-xs py-1.5 px-3 mx-auto">
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Retry Request</span>
            </button>
          </div>
        )}

        {/* State 3: Malformed Response Data */}
        {isMalformed && allEpisodes.length === 0 && (
          <div className="card p-8 border-warn/30 bg-warn/5 text-center">
            <FileQuestion className="w-7 h-7 mx-auto text-warn mb-3" />
            <p className="text-sm font-semibold text-warn">Malformed Episode Response Structure</p>
            <p className="text-xs text-muted max-w-md mx-auto mt-1">
              The backend returned an unexpected response schema from <code className="text-ink font-mono">/v1/assets/{assetId}/episodes</code>.
            </p>
          </div>
        )}

        {/* State 4: Genuine Empty Response (0 episodes, Nominal) */}
        {!isLoading && !fetchError && !isMalformed && allEpisodes.length === 0 && (
          <div className="card-muted p-10 text-center">
            <span className="chip chip-ok mb-3">
              <CheckCircle2 className="w-3 h-3 text-ok" /> Nominal
            </span>
            <p className="card-title">No anomaly episodes recorded</p>
            <p className="text-xs text-muted max-w-md mx-auto mt-1">
              Zero active or historical anomaly episodes detected for asset <strong className="font-mono text-ink">{assetId}</strong>.
              All multi-domain statistical and physics detectors are operating within nominal thresholds.
            </p>
          </div>
        )}

        {/* State 5: Filtered empty */}
        {allEpisodes.length > 0 && filteredEpisodes.length === 0 && (
          <div className="card-muted p-8 text-center text-xs text-muted">
            <p className="font-medium text-ink">No episodes match active filter ({stateFilter !== 'ALL' ? stateFilter : ''} {categoryFilter !== 'ALL' ? categoryFilter : ''})</p>
            <button
              onClick={() => { setStateFilter('ALL'); setCategoryFilter('ALL'); }}
              className="link mt-2 text-xs"
            >
              Clear filters to view all {allEpisodes.length} episodes
            </button>
          </div>
        )}

        {/* State 6: Episodes Loaded and Rendered */}
        {filteredEpisodes.length > 0 && (
          <div className="card divide-y divide-line overflow-hidden">
            {filteredEpisodes.map((ep) => {
              const stateUpper = String(ep.state).toUpperCase();
              const isCrit = stateUpper === 'CRITICAL';
              const isWarn = stateUpper === 'WARNING';
              const isClosed = stateUpper === 'CLOSED';

              return (
                <div
                  key={ep.episode_id}
                  className="relative p-5 pl-6 hover:bg-surface-2 transition-colors"
                >
                  <span
                    className={`absolute left-0 top-0 bottom-0 w-[3px] ${
                      isCrit ? 'bg-crit' : isWarn ? 'bg-warn' : isClosed ? 'bg-line-strong' : 'bg-accent'
                    }`}
                  />
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <AlertTriangle
                        className={`w-4 h-4 mt-0.5 flex-shrink-0 ${
                          isCrit ? 'text-crit' : isWarn ? 'text-warn' : isClosed ? 'text-muted' : 'text-accent'
                        }`}
                        strokeWidth={1.75}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`chip ${
                              isCrit ? 'chip-crit' : isWarn ? 'chip-warn' : isClosed ? 'chip-neutral' : 'chip-accent'
                            }`}
                          >
                            {stateUpper}
                          </span>
                          <span className="text-[11px] font-mono text-muted">{ep.episode_id}</span>
                          <span className="text-faint">·</span>
                          <span className="text-xs font-semibold text-ink-2">{ep.category}</span>
                          {ep.asset_id && (
                            <>
                              <span className="text-faint">·</span>
                              <span className="font-mono text-[11px] text-muted">{ep.asset_id}</span>
                            </>
                          )}
                          {ep.is_monitoring_gap && (
                            <span className="chip chip-outline text-[10px] text-warn">
                              Data Gap Frozen
                            </span>
                          )}
                        </div>

                        <h3 className="card-title mt-2 font-medium text-ink">
                          {ep.primary_reason || 'Anomaly trigger event'}
                        </h3>

                        {/* Evidence IDs & Hypothesis Codes */}
                        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs">
                          {ep.evidence_ids && ep.evidence_ids.length > 0 && (
                            <div className="flex items-center gap-1.5 text-muted">
                              <Layers className="w-3.5 h-3.5 text-faint" />
                              <span className="font-mono text-[11px]">
                                {ep.evidence_ids.length} Evidence {ep.evidence_ids.length === 1 ? 'Item' : 'Items'} ({ep.evidence_ids.slice(0, 3).join(', ')}{ep.evidence_ids.length > 3 ? '...' : ''})
                              </span>
                            </div>
                          )}

                          {ep.hypothesis_codes && ep.hypothesis_codes.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1">
                              <span className="eyebrow text-[10px] mr-0.5">Hypotheses:</span>
                              {ep.hypothesis_codes.map((code) => (
                                <span
                                  key={code}
                                  className="px-1.5 py-0.5 rounded font-mono text-[10px] text-ink-2 border border-line bg-surface-2"
                                >
                                  {code}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="sm:text-right flex-shrink-0 pl-7 sm:pl-0">
                      <span className="eyebrow text-[11px]">Severity Score</span>
                      <div className="metric-value text-[26px] mt-1 text-ink">
                        {typeof ep.severity_score === 'number'
                          ? (ep.severity_score * 100).toFixed(0)
                          : '—'}
                        <span className="metric-unit ml-0.5">%</span>
                      </div>
                      <div className="text-[11px] font-mono text-muted mt-1.5 space-y-0.5">
                        <div>Start: {formatUtcTime(ep.start_time_utc)}</div>
                        {ep.last_seen_time_utc && ep.last_seen_time_utc !== ep.start_time_utc && (
                          <div>Last Seen: {formatUtcTime(ep.last_seen_time_utc)}</div>
                        )}
                        {ep.closed_time_utc && (
                          <div className="text-ok">Closed: {formatUtcTime(ep.closed_time_utc)}</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* CUSUM Statistical Drift Tracker */}
      <div>
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
          <h2 className="section-title">Statistical drift detector</h2>
          <span className={`chip ${isCusumQualified ? 'chip-ok' : 'chip-outline'} font-mono`}>
            {isCusumQualified ? 'Qualified / Active' : 'Frozen / Disabled'}
          </span>
        </div>
        <div className="card p-5">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-4 border-b border-line">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                <span className="eyebrow">Statistical Drift Detector</span>
                <span className={`chip ${isCusumQualified ? 'chip-ok' : 'chip-neutral'} font-mono`}>
                  {isCusumQualified ? 'ACTIVE — QUALIFIED' : 'DISABLED — NOT QUALIFIED'}
                </span>
              </div>
              <h3 className="card-title">Two-Sided Robust CUSUM Accumulator (Thermal Residual)</h3>
              <p className="text-xs text-muted mt-1">
                {isCusumQualified
                  ? 'Two-sided CUSUM tracker operating on calibrated model residuals with decision threshold h=5.0.'
                  : `Thermal residual anomaly detection is not qualified for asset ${twinState?.asset_id || 'unpromoted'}. Only promoted model artifacts qualify for statistical residual tracking.`}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-line border border-line rounded-card overflow-hidden mt-4">
            {[
              {
                label: 'Positive Accumulator (C⁺)',
                value: isCusumQualified && twinState?.detector_state ? twinState.detector_state.cusum_pos.toFixed(2) : '—',
                note: isCusumQualified ? 'Decision threshold: h=5.00' : 'Decision threshold: — (Disabled)',
              },
              {
                label: 'Negative Accumulator (C⁻)',
                value: isCusumQualified && twinState?.detector_state ? Math.abs(twinState.detector_state.cusum_neg).toFixed(2) : '—',
                note: isCusumQualified ? 'Lower threshold: h=-5.00' : 'Lower threshold: — (Disabled)',
              },
              {
                label: 'Persistence Window',
                value: isCusumQualified && twinState?.detector_state?.cusum_alarm_active ? 'ALARM' : (isCusumQualified ? 'NOMINAL' : '—'),
                note: isCusumQualified ? 'Gate status: Active monitoring' : 'Gate status: Inactive',
              },
            ].map((c) => (
              <div key={c.label} className="bg-surface-2 p-4">
                <span className="eyebrow text-[11px] block">{c.label}</span>
                <div className={`metric-value text-[28px] ${isCusumQualified ? 'font-semibold text-ink' : 'font-normal text-faint'} mt-3`}>
                  {c.value}
                </div>
                <span className="text-[11px] text-muted mt-2 block">{c.note}</span>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <button
              onClick={() => setShowDetectorMath(!showDetectorMath)}
              className="link inline-flex items-center gap-1"
            >
              <span>{showDetectorMath ? 'Hide detector details' : 'How does the CUSUM detector work?'}</span>
              {showDetectorMath ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>

            {showDetectorMath && (
              <div className="mt-3 text-xs text-ink-2 bg-surface-2 p-4 rounded-card border border-line space-y-1.5 leading-relaxed">
                <p>
                  <strong className="font-semibold text-ink">Algorithm:</strong> Cumulative sum of normalized thermal residuals: <span className="font-mono text-ink">C⁺_k = max(0, C⁺_{`k-1`} + (r_k - μ) / σ - k_drift)</span>.
                </p>
                <p>
                  Filters out high-frequency sensor noise while reliably detecting sustained upward or downward thermal shifts caused by overloading or cooling degradation.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
