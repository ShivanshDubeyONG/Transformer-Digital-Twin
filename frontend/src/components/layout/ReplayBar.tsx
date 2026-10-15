import React from 'react';
import {
  Play,
  Pause,
  StepBack,
  StepForward,
  RotateCcw,
  Clock,
  Database,
  Zap,
  PanelLeftOpen,
} from 'lucide-react';
import { ReplayStatusResponse } from '../../types/contracts';
import { getAssetContext, ALL_CPRI_ASSETS, CPRI_ASSET_RATINGS } from '../../utils/assetContext';

interface ReplayBarProps {
  selectedDataset: string;
  onDatasetChange: (dataset: string) => void;
  assetId: string;
  onAssetChange?: (assetId: string) => void;
  isTwinStarted: boolean;
  onStartTwin: () => void;
  replayStatus: ReplayStatusResponse | null;
  isPlaying: boolean;
  onPlayToggle: () => void;
  onNext: (batchSize?: number) => void;
  onPrevious?: () => void;
  speedMultiplier: number;
  onSpeedChange: (speed: number) => void;
  onReset: () => void;
  isBackendHealthy: boolean;
  isSidebarOpen?: boolean;
  onToggleSidebar?: () => void;
}

export const ReplayBar: React.FC<ReplayBarProps> = ({
  selectedDataset,
  onDatasetChange,
  assetId,
  onAssetChange,
  isTwinStarted,
  onStartTwin,
  replayStatus,
  isPlaying,
  onPlayToggle,
  onNext,
  onPrevious,
  speedMultiplier,
  onSpeedChange,
  onReset,
  isBackendHealthy,
  isSidebarOpen = true,
  onToggleSidebar,
}) => {
  const assetContext = getAssetContext(assetId);
  const processed = replayStatus?.processed_events ?? 0;
  const total =
    replayStatus?.total_events && replayStatus.total_events > 0
      ? replayStatus.total_events.toLocaleString()
      : '3,659';

  // Format timestamp: if processed is 0 or current_time_utc is missing, wait for first frame
  const currentTime = replayStatus?.current_time_utc;
  const hasFrames = processed > 0 && Boolean(currentTime);
  const formattedTime = hasFrames && currentTime
    ? new Date(currentTime).toISOString().replace('T', ' ').slice(0, 19) + ' UTC'
    : 'Waiting for first telemetry frame';

  const progressPct =
    replayStatus?.total_events && replayStatus.total_events > 0
      ? Math.min(100, (processed / replayStatus.total_events) * 100)
      : 0;

  return (
    <div className="card mb-6">
      {/* Top Row: Asset / Dataset Identity & Twin Lifecycle */}
      <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2.5 px-4 sm:px-5 py-3 border-b border-line">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 min-w-0">
          {!isSidebarOpen && onToggleSidebar && (
            <button
              onClick={onToggleSidebar}
              className="hidden lg:flex items-center gap-1.5 h-8 px-2.5 rounded border border-line bg-surface-2 hover:bg-surface text-ink hover:text-accent text-[12px] font-medium transition-colors shadow-xs"
              title="Open navigation sidebar"
              id="replay-open-sidebar-btn"
            >
              <PanelLeftOpen className="w-3.5 h-3.5 text-accent" />
              <span>Sidebar</span>
            </button>
          )}

          <div className="flex items-center gap-2 min-w-0">
            <span
              className={`dot w-2 h-2 ${isBackendHealthy ? 'bg-ok' : 'bg-crit'}`}
              title={isBackendHealthy ? 'Connected to digital twin server' : 'Backend offline'}
            />
            <label
              htmlFor="replay-dataset-select"
              className="eyebrow flex items-center gap-1.5"
            >
              <Database className="w-3.5 h-3.5" strokeWidth={1.75} />
              Dataset
            </label>
            <select
              id="replay-dataset-select"
              value={selectedDataset}
              onChange={(e) => onDatasetChange(e.target.value)}
              className="input h-8 w-auto max-w-[280px] sm:max-w-none py-0 px-2.5 pr-7 cursor-pointer font-medium text-[12px]"
            >
              <option value="cpri_v3_0_2">CPRI Synthetic Benchmark v3.0.2 (Baseline)</option>
              <option value="gridpulse_synthetic_v1">GridPulse Synthetic v1.0.0 (Candidate)</option>
            </select>
          </div>

          {/* Contextual Asset Identity with interactive Transformer selector */}
          <div className="flex items-center gap-2 pl-4 border-l border-line">
            <label htmlFor="replay-asset-select" className="eyebrow flex items-center gap-1.5">
              <Zap className="w-3.5 h-3.5 text-accent" strokeWidth={1.75} />
              Transformer
            </label>
            {onAssetChange ? (
              <select
                id="replay-asset-select"
                value={assetId}
                onChange={(e) => onAssetChange(e.target.value)}
                className="input h-8 w-auto py-0 px-2.5 pr-7 cursor-pointer font-mono text-[12px] font-semibold text-ink"
                title="Select transformer asset"
              >
                {selectedDataset === 'gridpulse_synthetic_v1' ? (
                  <>
                    <option value="DT-01">DT-01 (250 kVA · Conservator) · Promoted Candidate</option>
                    <option value="DT-02">DT-02 (500 kVA · Conservator) · Unpromoted Candidate</option>
                    <option value="DT-03">DT-03 (250 kVA · Sealed Corr.) · Unpromoted Candidate</option>
                    <option value="DT-04">DT-04 (160 kVA · Conservator) · Unpromoted Candidate</option>
                  </>
                ) : (
                  ALL_CPRI_ASSETS.map((id) => (
                    <option key={id} value={id}>
                      {id} ({CPRI_ASSET_RATINGS[id]} kVA){id === 'TX_1000_COMM' ? ' · Promoted Baseline' : ' · Unpromoted'}
                    </option>
                  ))
                )}
              </select>
            ) : (
              <span className="font-mono text-[11px] font-medium text-ink">
                {assetId} · {assetContext.siteLabel}
              </span>
            )}

            <span
              className={`chip ${
                assetContext.promotionStatus === 'PROMOTED' ? 'chip-ok' : 'chip-neutral'
              } text-[10.5px] font-medium hidden sm:inline-flex`}
            >
              {assetContext.promotionStatus === 'PROMOTED' ? (
                <>
                  <span className="dot bg-ok" />
                  <span>{assetContext.isCandidate ? 'Promoted Candidate' : 'Promoted Baseline'}</span>
                </>
              ) : (
                <span>{assetContext.isCandidate ? 'Unpromoted Candidate' : 'Unpromoted Baseline'}</span>
              )}
            </span>
          </div>
        </div>

        {/* Digital Twin Lifecycle Status & Start Action */}
        <div className="flex items-center gap-3">
          {!isTwinStarted ? (
            <>
              <span className="text-xs text-muted hidden 2xl:inline max-w-sm text-right">
                Replay telemetry through the digital twin one {assetContext.cadenceLabel} measurement at a time.
              </span>
              <span className="chip chip-neutral">Ready to start</span>
              <button onClick={onStartTwin} className="btn btn-primary h-8 px-3.5">
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Start Digital Twin</span>
              </button>
            </>
          ) : replayStatus?.is_completed ? (
            <span className="chip chip-neutral border-ok/30">
              <span className="dot bg-ok" />
              <span className="text-ok font-medium">CAL Partition Completed</span>
            </span>
          ) : (
            <span className={`chip ${isPlaying ? 'chip-ok' : 'chip-neutral'}`}>
              <span className={`dot ${isPlaying ? 'bg-ok animate-pulse' : 'bg-faint'}`} />
              <span>{isPlaying ? 'Twin Running' : 'Twin Paused'}</span>
            </span>
          )}
        </div>
      </div>

      {/* Bottom Row: Timestamp, Replay Controls & Frame Progress */}
      <div className="flex flex-wrap items-center justify-between gap-x-5 gap-y-2.5 px-4 sm:px-5 py-3">
        {/* Event Timestamp */}
        <div className="flex items-center gap-2.5 min-w-0">
          <Clock className="w-4 h-4 text-muted flex-shrink-0" strokeWidth={1.75} />
          {hasFrames ? (
            <span className="font-mono text-[12.5px] font-medium text-ink num">{formattedTime}</span>
          ) : (
            <span className="chip chip-neutral normal-case tracking-normal text-[11px] font-medium">
              {formattedTime}
            </span>
          )}
        </div>

        {/* Interactive Playback Controls - All unified to h-8 */}
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={onPlayToggle}
            title={isPlaying ? 'Pause automatic replay' : 'Play automatic replay'}
            className={`btn h-8 min-w-[80px] px-3 ${isPlaying ? 'btn-accent' : 'btn-primary'}`}
          >
            {isPlaying ? (
              <>
                <Pause className="w-3.5 h-3.5" />
                <span>Pause</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Play</span>
              </>
            )}
          </button>

          <div className="segmented h-8">
            <button
              onClick={onPrevious}
              disabled={!isTwinStarted || processed <= 0}
              title="Step back to previous telemetry frame"
              className="flex items-center gap-1.5 h-7 px-2.5"
            >
              <StepBack className="w-3.5 h-3.5" />
              <span>Prev</span>
            </button>
            <button
              onClick={() => onNext(1)}
              disabled={!isTwinStarted || Boolean(replayStatus?.is_completed)}
              title="Process exactly the next 1 telemetry frame"
              className="flex items-center gap-1.5 h-7 px-2.5"
            >
              <StepForward className="w-3.5 h-3.5" />
              <span>Next</span>
            </button>
            <button
              onClick={() => onNext(5)}
              disabled={!isTwinStarted || Boolean(replayStatus?.is_completed)}
              title="Process the next 5 telemetry frames"
              className="h-7 px-2.5"
            >
              +5
            </button>
          </div>

          <div className="hidden sm:inline-flex segmented h-8">
            {[
              { val: 1, label: '1×' },
              { val: 5, label: '5×' },
              { val: 10, label: '10×' },
            ].map(({ val, label }) => (
              <button
                key={label}
                onClick={() => onSpeedChange(val)}
                disabled={!isTwinStarted}
                title={`Advance replay at ${label} speed`}
                data-active={speedMultiplier === val}
                className="font-mono h-7 px-2.5"
              >
                {label}
              </button>
            ))}
          </div>

          <button
            onClick={onReset}
            disabled={!isTwinStarted && processed === 0}
            title="Reset replay to frame 0 and clear derived state"
            className="icon-btn w-8 h-8"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>

        {/* Frame Progress */}
        <div className="flex items-center gap-3 min-w-[180px]">
          <div className="flex-1 h-[3px] rounded-full bg-surface-3 overflow-hidden hidden sm:block">
            <div className="h-full bg-accent transition-all" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="text-[11px] font-mono text-muted whitespace-nowrap num">
            <span className="font-semibold text-ink">{processed.toLocaleString()}</span>
            <span> / {total} frames</span>
          </div>
        </div>
      </div>
    </div>
  );
};
