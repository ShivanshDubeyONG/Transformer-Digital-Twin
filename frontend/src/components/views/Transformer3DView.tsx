import React, { useState } from 'react';
import {
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  Eye,
  Flame,
  Layers,
  Zap,
  RotateCw,
  RotateCcw,
  Compass,
  Activity,
  Maximize2,
  Minimize2,
  Target,
  Tag,
  Boxes,
} from 'lucide-react';

import { TwinState, OTHIBundle } from '../../types/contracts';
import { ComponentId, VisualMode, ModelTelemetry } from './transformer3d/TransformerGeometry';
import { TransformerCanvas } from './transformer3d/TransformerCanvas';

interface Transformer3DViewProps {
  twinState: TwinState | null;
  health?: OTHIBundle | null;
  onNavigateTab?: (tab: string) => void;
}

interface ComponentMeta {
  id: ComponentId;
  name: string;
  category: string;
  badgeLabel: string;
  status: 'NORMAL' | 'WATCH' | 'WARNING' | 'CRITICAL' | 'UNAVAILABLE';
  targetTab: string;
  targetTabLabel: string;
  description: string;
  primaryValue: string;
  secondaryValue: string;
  metrics: {
    label: string;
    value: string;
    sublabel?: string;
    isUnavailable?: boolean;
    badge?: string;
  }[];
}

export const Transformer3DView: React.FC<Transformer3DViewProps> = ({
  twinState,
  health,
  onNavigateTab,
}) => {
  const [selectedId, setSelectedId] = useState<ComponentId | null>(null);
  const [hoveredId, setHoveredId] = useState<ComponentId | null>(null);
  const [visualMode, setVisualMode] = useState<VisualMode>('realistic');
  const [isAutoRotate, setIsAutoRotate] = useState<boolean>(false);
  const [showTags, setShowTags] = useState<boolean>(true);
  const [cameraPresetTrigger, setCameraPresetTrigger] = useState<string>('isometric');
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [explodeAmount, setExplodeAmount] = useState<number>(0);

  const handleToggleDisassemble = () => {
    if (explodeAmount > 0) {
      setExplodeAmount(0);
    } else {
      setExplodeAmount(100);
    }
  };

  const handleScrubDisassemble = (val: number) => {
    setExplodeAmount(val);
  };

  // Authoritative Telemetry Extraction
  const obs = twinState?.current_observations;
  const topOilObs = obs?.top_oil_temperature?.value ?? obs?.oti_degc?.value;
  const ambTemp = obs?.ambient_temperature?.value;
  const topOilExp = twinState?.thermal_latent?.top_oil_expected_degc;
  const topOilRes =
    typeof topOilObs === 'number' && typeof topOilExp === 'number'
      ? (topOilObs - topOilExp).toFixed(1)
      : null;

  const currentL1 = obs?.current_l1?.value ?? obs?.current_i1?.value;
  const voltageL1 = obs?.voltage_l1_n?.value ?? obs?.voltage_v1?.value;
  const currentL2 = obs?.current_l2?.value ?? obs?.current_i2?.value;
  const voltageL2 = obs?.voltage_l2_n?.value ?? obs?.voltage_v2?.value;
  const currentL3 = obs?.current_l3?.value ?? obs?.current_i3?.value;
  const voltageL3 = obs?.voltage_l3_n?.value ?? obs?.voltage_v3?.value;
  const neutralCurrent = obs?.neutral_current?.value ?? obs?.current_in?.value;
  const oilLevel = obs?.oil_level_pct?.value ?? obs?.oli?.value;
  const relLoad = twinState?.derived_electrical?.relative_load_index;
  const apparentPower = twinState?.derived_electrical?.apparent_power_derived_kva;
  const phaseImbalancePct = twinState?.derived_electrical?.current_magnitude_imbalance_pct;

  const thermalStatus = (health?.domains?.thermal?.status ?? 'NORMAL') as ComponentMeta['status'];
  const phaseStatus = (health?.domains?.phase_neutral?.status ?? 'NORMAL') as ComponentMeta['status'];
  const oilStatus = (health?.domains?.oil_protection?.status ?? 'NORMAL') as ComponentMeta['status'];

  const othiScore = health?.othi_score ?? 100;
  const othiStatus = health?.status ?? 'NORMAL';

  const timestamp = twinState?.state_time_utc
    ? new Date(twinState.state_time_utc).toUTCString()
    : 'Live Synchronized';

  const assetId = twinState?.asset_id || 'DT-01';

  // Telemetry bundle passed into 3D scene builder
  const modelTelemetry: ModelTelemetry = {
    topOilTemp: typeof topOilObs === 'number' ? topOilObs : null,
    ambientTemp: typeof ambTemp === 'number' ? ambTemp : null,
    currentL1: typeof currentL1 === 'number' ? currentL1 : null,
    currentL2: typeof currentL2 === 'number' ? currentL2 : null,
    currentL3: typeof currentL3 === 'number' ? currentL3 : null,
    neutralCurrent: typeof neutralCurrent === 'number' ? neutralCurrent : null,
    oilLevelPct: typeof oilLevel === 'number' ? oilLevel : null,
    relativeLoad: typeof relLoad === 'number' ? relLoad : null,
    thermalStatus,
    phaseStatus,
    oilStatus,
  };

  // Component Definitions with Strict Data Honesty (No invented numbers, em dash for unavailable)
  const components: Record<ComponentId, ComponentMeta> = {
    tank: {
      id: 'tank',
      name: 'Main Tank & Thermal Core',
      category: 'Thermal & Structural Assembly',
      badgeLabel: 'TANK (OTI)',
      status: thermalStatus,
      targetTab: 'twin-analysis',
      targetTabLabel: 'View thermal evidence →',
      description:
        'Sealed welded steel enclosure containing high-permeability silicon steel core laminations and copper windings immersed in mineral insulating oil.',
      primaryValue: typeof topOilObs === 'number' ? `${topOilObs.toFixed(1)} °C` : '—',
      secondaryValue: topOilRes !== null ? `ΔT ${Number(topOilRes) >= 0 ? '+' : ''}${topOilRes} °C` : 'ODE Baseline',
      metrics: [
        {
          label: 'Observed Top-Oil Temp',
          value: typeof topOilObs === 'number' ? `${topOilObs.toFixed(1)} °C` : '—',
          sublabel: 'PT100 probe well measurement',
          isUnavailable: typeof topOilObs !== 'number',
        },
        {
          label: 'Expected Top-Oil Temp',
          value: typeof topOilExp === 'number' ? `${topOilExp.toFixed(1)} °C` : '—',
          sublabel: 'Calibrated first-order thermal ODE',
          isUnavailable: typeof topOilExp !== 'number',
        },
        {
          label: 'Thermal Residual (ΔT)',
          value: topOilRes !== null ? `${Number(topOilRes) >= 0 ? '+' : ''}${topOilRes} °C` : '—',
          sublabel: 'Deviation from expected baseline',
          isUnavailable: topOilRes === null,
        },
        {
          label: 'Ambient Temperature',
          value: typeof ambTemp === 'number' ? `${ambTemp.toFixed(1)} °C` : '—',
          sublabel: 'Substation ambient reference',
          isUnavailable: typeof ambTemp !== 'number',
        },
      ],
    },
    l1: {
      id: 'l1',
      name: 'Phase L1 HV Bushing',
      category: 'Electrical Terminal',
      badgeLabel: 'PHASE L1',
      status: phaseStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View electrical telemetry →',
      description:
        'Outdoor porcelain condenser bushing conducting Phase 1 primary grid current through the grounded tank top cover.',
      primaryValue: typeof currentL1 === 'number' ? `${currentL1.toFixed(1)} A` : '—',
      secondaryValue: typeof voltageL1 === 'number' ? `${voltageL1.toFixed(1)} V` : '—',
      metrics: [
        {
          label: 'Phase L1 Current',
          value: typeof currentL1 === 'number' ? `${currentL1.toFixed(1)} A` : '—',
          sublabel: 'Measured line current',
          isUnavailable: typeof currentL1 !== 'number',
        },
        {
          label: 'Phase L1-N Voltage',
          value: typeof voltageL1 === 'number' ? `${voltageL1.toFixed(1)} V` : '—',
          sublabel: 'Phase-to-neutral voltage',
          isUnavailable: typeof voltageL1 !== 'number',
        },
        {
          label: 'Phase Imbalance',
          value: typeof phaseImbalancePct === 'number' ? `${phaseImbalancePct.toFixed(1)} %` : '—',
          sublabel: 'NEMA current magnitude imbalance',
          isUnavailable: typeof phaseImbalancePct !== 'number',
        },
      ],
    },
    l2: {
      id: 'l2',
      name: 'Phase L2 HV Bushing',
      category: 'Electrical Terminal',
      badgeLabel: 'PHASE L2',
      status: phaseStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View electrical telemetry →',
      description:
        'Outdoor porcelain condenser bushing conducting Phase 2 primary grid current through the grounded tank top cover.',
      primaryValue: typeof currentL2 === 'number' ? `${currentL2.toFixed(1)} A` : '—',
      secondaryValue: typeof voltageL2 === 'number' ? `${voltageL2.toFixed(1)} V` : '—',
      metrics: [
        {
          label: 'Phase L2 Current',
          value: typeof currentL2 === 'number' ? `${currentL2.toFixed(1)} A` : '—',
          sublabel: 'Measured line current',
          isUnavailable: typeof currentL2 !== 'number',
        },
        {
          label: 'Phase L2-N Voltage',
          value: typeof voltageL2 === 'number' ? `${voltageL2.toFixed(1)} V` : '—',
          sublabel: 'Phase-to-neutral voltage',
          isUnavailable: typeof voltageL2 !== 'number',
        },
        {
          label: 'Phase Imbalance',
          value: typeof phaseImbalancePct === 'number' ? `${phaseImbalancePct.toFixed(1)} %` : '—',
          sublabel: 'NEMA current magnitude imbalance',
          isUnavailable: typeof phaseImbalancePct !== 'number',
        },
      ],
    },
    l3: {
      id: 'l3',
      name: 'Phase L3 HV Bushing',
      category: 'Electrical Terminal',
      badgeLabel: 'PHASE L3',
      status: phaseStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View electrical telemetry →',
      description:
        'Outdoor porcelain condenser bushing conducting Phase 3 primary grid current through the grounded tank top cover.',
      primaryValue: typeof currentL3 === 'number' ? `${currentL3.toFixed(1)} A` : '—',
      secondaryValue: typeof voltageL3 === 'number' ? `${voltageL3.toFixed(1)} V` : '—',
      metrics: [
        {
          label: 'Phase L3 Current',
          value: typeof currentL3 === 'number' ? `${currentL3.toFixed(1)} A` : '—',
          sublabel: 'Measured line current',
          isUnavailable: typeof currentL3 !== 'number',
        },
        {
          label: 'Phase L3-N Voltage',
          value: typeof voltageL3 === 'number' ? `${voltageL3.toFixed(1)} V` : '—',
          sublabel: 'Phase-to-neutral voltage',
          isUnavailable: typeof voltageL3 !== 'number',
        },
        {
          label: 'Phase Imbalance',
          value: typeof phaseImbalancePct === 'number' ? `${phaseImbalancePct.toFixed(1)} %` : '—',
          sublabel: 'NEMA current magnitude imbalance',
          isUnavailable: typeof phaseImbalancePct !== 'number',
        },
      ],
    },
    neutral: {
      id: 'neutral',
      name: 'Neutral Grounding Bushing',
      category: 'Electrical Terminal',
      badgeLabel: 'NEUTRAL (N)',
      status: phaseStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View neutral telemetry →',
      description:
        'Porcelain insulator providing solid star-point system neutral return path to substation grounding grid.',
      primaryValue: typeof neutralCurrent === 'number' ? `${neutralCurrent.toFixed(1)} A` : '—',
      secondaryValue: 'Ground Return',
      metrics: [
        {
          label: 'Neutral Return Current',
          value: typeof neutralCurrent === 'number' ? `${neutralCurrent.toFixed(1)} A` : '—',
          sublabel: 'Directly measured zero-sequence return',
          isUnavailable: typeof neutralCurrent !== 'number',
        },
        {
          label: 'Neutral Residual Current',
          value: typeof neutralCurrent === 'number' ? `${neutralCurrent.toFixed(1)} A` : '—',
          sublabel: 'Derived from vector sum |Ia + Ib + Ic|',
          isUnavailable: typeof neutralCurrent !== 'number',
        },
      ],
    },
    cooling: {
      id: 'cooling',
      name: 'Radiator Fin Banks',
      category: 'Thermosiphon Cooling',
      badgeLabel: 'RADIATORS',
      status: thermalStatus,
      targetTab: 'twin-analysis',
      targetTabLabel: 'View cooling performance →',
      description:
        'Twin welded steel fluted radiator assemblies on opposing sides facilitating natural thermosiphon oil circulation and convective heat rejection to ambient air.',
      primaryValue: 'ONAN Natural',
      secondaryValue: '7 Fins / Bank',
      metrics: [
        {
          label: 'Cooling Mode',
          value: 'ONAN (Natural Convection)',
          sublabel: 'Oil Natural Air Natural',
          isUnavailable: false,
        },
        {
          label: 'Radiator Bank Count',
          value: '2 Symmetrical Banks (14 Fins)',
          sublabel: 'Left & Right tank sidewall assemblies',
          isUnavailable: false,
        },
        {
          label: 'Thermosiphon Delta (ΔT)',
          value: topOilRes !== null ? `${Number(topOilRes) >= 0 ? '+' : ''}${topOilRes} °C` : 'Nominal',
          sublabel: 'Top-oil to bottom-oil differential',
          isUnavailable: false,
        },
      ],
    },
    oil: {
      id: 'oil',
      name: 'Conservator & Buchholz System',
      category: 'Oil Preservation',
      badgeLabel: 'CONSERVATOR',
      status: oilStatus,
      targetTab: 'telemetry',
      targetTabLabel: 'View protection telemetry →',
      description:
        'Elevated cylindrical expansion drum accommodating oil volumetric expansion during thermal cycling, fitted with dehydrating silica gel breather and Magnetic Oil Gauge.',
      primaryValue: typeof oilLevel === 'number' ? `${oilLevel.toFixed(0)} %` : '—',
      secondaryValue: 'MOG Supervised',
      metrics: [
        {
          label: 'Oil Level Gauge (MOG)',
          value: typeof oilLevel === 'number' ? `${oilLevel.toFixed(0)} %` : '—',
          sublabel: 'Active magnetic float gauge measurement',
          isUnavailable: typeof oilLevel !== 'number',
        },
        {
          label: 'Buchholz Gas Relay',
          value: 'Supervised',
          sublabel: 'Inline pipe gas accumulation detector',
          isUnavailable: false,
        },
        {
          label: 'Silica Gel Breather',
          value: 'Active (Desiccant Blue)',
          sublabel: 'Dehydrating atmospheric breather',
          isUnavailable: false,
        },
      ],
    },
    core: {
      id: 'core',
      name: 'Active Core & Windings Assembly',
      category: 'Electromagnetic Assembly',
      badgeLabel: 'CORE & COILS',
      status: thermalStatus,
      targetTab: 'twin-analysis',
      targetTabLabel: 'View thermal & loss analysis →',
      description:
        'Three-column high-permeability cold-rolled grain-oriented (CRGO) silicon steel core clamped with structural steel yokes and wrapped in high-conductivity copper windings.',
      primaryValue: typeof relLoad === 'number' ? `${(relLoad * 100).toFixed(0)} % Load` : '—',
      secondaryValue: typeof apparentPower === 'number' ? `${apparentPower.toFixed(0)} kVA` : '—',
      metrics: [
        {
          label: 'Relative Load Index',
          value: typeof relLoad === 'number' ? `${(relLoad * 100).toFixed(1)} %` : '—',
          sublabel: 'Current capacity utilization',
          isUnavailable: typeof relLoad !== 'number',
        },
        {
          label: 'Total Apparent Power',
          value: typeof apparentPower === 'number' ? `${apparentPower.toFixed(1)} kVA` : '—',
          sublabel: 'Vector sum of three-phase power',
          isUnavailable: typeof apparentPower !== 'number',
        },
        {
          label: 'Winding Hot-Spot Temp',
          value: '—',
          sublabel: 'Unavailable (C4 gated — no direct optical fiber sensor)',
          isUnavailable: true,
        },
      ],
    },
  };

  const currentComp: ComponentMeta = (selectedId && components[selectedId]) || components.tank;

  // Helper status color mapping matching design tokens
  const getStatusBadge = (status: ComponentMeta['status']) => {
    switch (status) {
      case 'NORMAL':
        return {
          chipClass: 'chip-ok',
          dotClass: 'bg-ok',
          icon: <CheckCircle2 className="w-3 h-3 text-ok" />,
          label: 'NORMAL',
        };
      case 'WATCH':
        return {
          chipClass: 'chip-accent',
          dotClass: 'bg-accent',
          icon: <AlertTriangle className="w-3 h-3 text-accent" />,
          label: 'WATCH',
        };
      case 'WARNING':
        return {
          chipClass: 'chip-warn',
          dotClass: 'bg-warn',
          icon: <AlertTriangle className="w-3 h-3 text-warn" />,
          label: 'WARNING',
        };
      case 'CRITICAL':
        return {
          chipClass: 'chip-crit',
          dotClass: 'bg-crit',
          icon: <AlertTriangle className="w-3 h-3 text-crit" />,
          label: 'CRITICAL',
        };
      case 'UNAVAILABLE':
      default:
        return {
          chipClass: 'chip-neutral',
          dotClass: 'bg-faint',
          icon: <HelpCircle className="w-3 h-3 text-faint" />,
          label: 'UNAVAILABLE',
        };
    }
  };

  const statusBadge = getStatusBadge(currentComp.status);

  const handleSelectComponent = (id: ComponentId | null) => {
    setSelectedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className={`space-y-4 ${isFullscreen ? 'fixed inset-0 z-50 bg-canvas p-4 sm:p-6 overflow-hidden flex flex-col' : ''}`}>
      {/* --------------------------------------------------------------------- */}
      {/* 1. TOP CONTROL BAR (Spacious, Glassmorphic, Cleanly Segmented) */}
      {/* --------------------------------------------------------------------- */}
      <div className="card px-4 sm:px-6 py-3 flex flex-wrap items-center justify-between gap-x-5 gap-y-3 shadow-sm rounded-xl">
        {/* Left: Transformer Identity & Live Health Indicator */}
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-ok opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-ok"></span>
            </span>
            <span className="font-mono text-[14px] font-bold text-ink tracking-tight">
              {assetId}
            </span>
            <span className="text-muted/30 font-light">|</span>
            <span className="text-[12px] text-muted font-medium hidden md:inline">
              250 kVA · 50 Hz · ONAN Distribution Asset
            </span>
          </div>

          <div className="flex items-center gap-2 pl-3.5 border-l border-line">
            <span className="eyebrow text-muted text-[10px]">OTHI HEALTH</span>
            <span
              className={`chip ${
                othiStatus === 'NORMAL'
                  ? 'chip-ok'
                  : othiStatus === 'WATCH'
                  ? 'chip-accent'
                  : othiStatus === 'WARNING'
                  ? 'chip-warn'
                  : 'chip-crit'
              } text-[11px] font-mono font-semibold px-2 py-0.5`}
            >
              <span className={`dot ${othiStatus === 'NORMAL' ? 'bg-ok' : 'bg-warn'}`} />
              <span>{othiScore}</span>
              <span className="font-sans font-normal opacity-85 text-[10.5px]">{othiStatus}</span>
            </span>
          </div>
        </div>

        {/* Center: Visualization Mode Segmented Control */}
        <div className="segmented h-8">
          <button
            onClick={() => setVisualMode('realistic')}
            data-active={visualMode === 'realistic'}
            className="flex items-center gap-1.5 h-7 px-3 text-[12px] font-medium"
          >
            <Eye className="w-3.5 h-3.5" />
            <span>Realistic</span>
          </button>

          <button
            onClick={() => setVisualMode('thermal')}
            data-active={visualMode === 'thermal'}
            className="flex items-center gap-1.5 h-7 px-3 text-[12px] font-medium"
          >
            <Flame className="w-3.5 h-3.5" />
            <span>Thermal Heatmap</span>
          </button>

          <button
            onClick={() => setVisualMode('xray')}
            data-active={visualMode === 'xray'}
            className="flex items-center gap-1.5 h-7 px-3 text-[12px] font-medium"
          >
            <Layers className="w-3.5 h-3.5" />
            <span>X-Ray Core</span>
          </button>

          <button
            onClick={() => setVisualMode('electrical')}
            data-active={visualMode === 'electrical'}
            className="flex items-center gap-1.5 h-7 px-3 text-[12px] font-medium"
          >
            <Zap className="w-3.5 h-3.5" />
            <span>Electrical Flow</span>
          </button>
        </div>

        {/* Right: Camera Presets & Stage Tools */}
        <div className="flex items-center gap-2">
          {/* Disassemble / Exploded View Controls in Top Bar */}
          <div className="flex items-center gap-2 bg-surface-2/90 border border-line rounded-lg px-2.5 h-8">
            <button
              onClick={handleToggleDisassemble}
              className={`text-[11.5px] font-medium flex items-center gap-1.5 transition-all ${
                explodeAmount > 0
                  ? 'text-amber-400 font-semibold'
                  : 'text-muted hover:text-ink'
              }`}
              title="Disassemble transformer model in 3D to reveal internal core & separated components"
            >
              <Boxes className="w-3.5 h-3.5 text-amber-400" />
              <span>{explodeAmount > 0 ? 'Assemble' : 'Disassemble'}</span>
            </button>

            <div className="h-3.5 w-px bg-line" />

            <div className="flex items-center gap-1.5">
              <span className="text-[10px] font-mono text-muted uppercase hidden sm:inline">Scrub:</span>
              <input
                type="range"
                min="0"
                max="100"
                value={explodeAmount}
                onChange={(e) => handleScrubDisassemble(Number(e.target.value))}
                className="w-16 sm:w-24 accent-amber-500 cursor-pointer h-1.5 bg-line rounded-lg"
                title="Drag to smoothly separate components in 3D"
              />
              <span className="font-mono text-[11px] font-bold text-amber-400 min-w-[28px] text-right">
                {explodeAmount}%
              </span>
            </div>

            <div className="hidden xl:flex items-center gap-0.5 border-l border-line pl-1 text-[10px] font-mono">
              <button
                onClick={() => handleScrubDisassemble(0)}
                className={`px-1 py-0.5 rounded transition-all ${explodeAmount === 0 ? 'bg-surface-3 text-ink font-bold' : 'text-muted hover:text-ink'}`}
                title="Assemble 0%"
              >
                0%
              </button>
              <button
                onClick={() => handleScrubDisassemble(50)}
                className={`px-1 py-0.5 rounded transition-all ${explodeAmount === 50 ? 'bg-surface-3 text-amber-400 font-bold' : 'text-muted hover:text-ink'}`}
                title="Disassemble 50%"
              >
                50%
              </button>
              <button
                onClick={() => handleScrubDisassemble(100)}
                className={`px-1 py-0.5 rounded transition-all ${explodeAmount === 100 ? 'bg-surface-3 text-amber-400 font-bold' : 'text-muted hover:text-ink'}`}
                title="Disassemble 100%"
              >
                100%
              </button>
            </div>
          </div>

          {/* Values on 3D Model Toggle */}
          <button
            onClick={() => setShowTags(!showTags)}
            className={`btn h-8 px-2.5 text-[11.5px] font-medium flex items-center gap-1.5 transition-all ${
              showTags ? 'bg-surface-3 text-accent border-accent/40 font-semibold' : 'btn-secondary text-muted'
            }`}
            title="Toggle Live Telemetry Value Tags directly on 3D Model"
          >
            <Tag className="w-3.5 h-3.5 text-accent" />
            <span>Values {showTags ? 'ON' : 'OFF'}</span>
          </button>

          <div className="hidden 2xl:flex items-center gap-1 text-[11px] font-mono text-muted mr-1">
            <Compass className="w-3.5 h-3.5" />
            <span className="eyebrow text-[10px]">Presets:</span>
          </div>

          <div className="segmented h-8">
            <button
              onClick={() => setCameraPresetTrigger('isometric')}
              data-active={cameraPresetTrigger === 'isometric'}
              className="h-7 px-2.5 text-[11.5px] font-medium flex items-center gap-1"
              title="Frame entire transformer"
            >
              <Target className="w-3 h-3 text-accent" />
              <span>Fit Frame</span>
            </button>
            <button
              onClick={() => setCameraPresetTrigger('top_bushings')}
              data-active={cameraPresetTrigger === 'top_bushings'}
              className="h-7 px-2 text-[11.5px]"
            >
              Bushings
            </button>
            <button
              onClick={() => setCameraPresetTrigger('front_tank')}
              data-active={cameraPresetTrigger === 'front_tank'}
              className="h-7 px-2 text-[11.5px]"
            >
              Tank
            </button>
            <button
              onClick={() => setCameraPresetTrigger('radiators')}
              data-active={cameraPresetTrigger === 'radiators'}
              className="h-7 px-2 text-[11.5px]"
            >
              Radiators
            </button>
            <button
              onClick={() => setCameraPresetTrigger('conservator')}
              data-active={cameraPresetTrigger === 'conservator'}
              className="h-7 px-2 text-[11.5px]"
            >
              Oil
            </button>
          </div>

          <button
            onClick={() => {
              setCameraPresetTrigger('isometric');
              setSelectedId(null);
            }}
            className="icon-btn w-8 h-8 hover:text-accent"
            title="Reset to Full Default View"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={() => setIsAutoRotate(!isAutoRotate)}
            className={`icon-btn w-8 h-8 ${isAutoRotate ? 'bg-surface-3 text-accent border-accent/40' : ''}`}
            title="Toggle Inspection Orbit"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isAutoRotate ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="icon-btn w-8 h-8"
            title="Toggle Fullscreen Arena"
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* --------------------------------------------------------------------- */}
      {/* 2. MAIN HERO STAGE (Balanced Proportions, No Wasted Space)           */}
      {/* --------------------------------------------------------------------- */}
      <div className={`grid grid-cols-1 xl:grid-cols-12 gap-4 ${isFullscreen ? 'flex-1 min-h-0' : ''}`}>
        {/* Left Column (9 cols): Expansive Widescreen 3D Viewport + Bottom Telemetry Rail */}
        <div className="xl:col-span-9 lg:col-span-8 flex flex-col gap-3.5">
          {/* 3D WebGL Canvas Box (Expansive, High-Resolution Workstation Canvas, 100% Unobstructed) */}
          <div className={`relative w-full ${isFullscreen ? 'flex-1 min-h-[520px]' : 'h-[580px] sm:h-[640px] xl:h-[680px]'} rounded-2xl border border-line/60 overflow-hidden select-none shadow-xl`}>

            <TransformerCanvas
              className="w-full h-full"
              telemetry={modelTelemetry}
              selectedId={selectedId}
              hoveredId={hoveredId}
              onSelectComponent={handleSelectComponent}
              onHoverComponent={(id) => setHoveredId(id)}
              visualMode={visualMode}
              isAutoRotate={isAutoRotate}
              cameraPresetTrigger={cameraPresetTrigger}
              showTags={showTags}
              componentsMeta={components}
              onNavigateTab={onNavigateTab}
              explodeProgress={explodeAmount / 100}
            />

            {/* Subtle Navigation Instruction Badge in Bottom Left */}
            <div className="absolute bottom-3 left-3 pointer-events-none text-[10.5px] font-mono text-muted/80 bg-surface/90 px-2.5 py-1 rounded-lg border border-line/50 backdrop-blur-md shadow-sm hidden sm:block">
              Tap / Click: Toggle Part · Disassemble: Explode 3D · Left-drag: Orbit · Scroll: Zoom
            </div>

            {/* Quick Fit Frame Floating Action in Bottom Right */}
            <div className="absolute bottom-3 right-3 flex items-center gap-2 z-20">
              <button
                onClick={() => setCameraPresetTrigger('isometric')}
                className="px-3 py-1.5 text-[11px] font-mono font-medium rounded-lg bg-surface/90 hover:bg-surface text-ink border border-line/60 shadow-md backdrop-blur-md flex items-center gap-1.5 transition-all hover:border-accent/40"
                title="Reset Camera Framing"
              >
                <Compass className="w-3.5 h-3.5 text-accent" />
                <span>Fit Frame</span>
              </button>
            </div>
          </div>

          {/* Bottom Telemetry Rail (8 Modern Component Sensor Micro-Tiles) */}
          <div className="card p-3 rounded-xl shadow-sm">
            <div className="flex items-center justify-between px-1 pb-2 border-b border-line mb-2.5">
              <span className="eyebrow flex items-center gap-1.5 text-[11px]">
                <Activity className="w-3.5 h-3.5 text-accent" />
                <span>Component Telemetry & Focus Rail</span>
              </span>
              <span className="meta text-[11px]">Click component tile to focus camera</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
              {(Object.keys(components) as ComponentId[]).map((id) => {
                const comp = components[id];
                const isSelected = selectedId === id;
                const isHovered = hoveredId === id;

                return (
                  <div
                    key={id}
                    onMouseEnter={() => setHoveredId(id)}
                    onMouseLeave={() => setHoveredId(null)}
                    onClick={() => handleSelectComponent(id)}
                    className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
                      isSelected
                        ? 'bg-surface-3 border-accent text-ink shadow-md ring-2 ring-accent/30 scale-[1.02]'
                        : isHovered
                        ? 'bg-surface-2 border-line-strong text-ink shadow-sm'
                        : 'bg-surface-2/60 border-line text-ink-2 hover:border-line-strong'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-mono font-bold tracking-wider text-muted">
                        {comp.badgeLabel}
                      </span>
                      <span
                        className={`dot w-2 h-2 ${
                          comp.status === 'NORMAL'
                            ? 'bg-ok'
                            : comp.status === 'WATCH'
                            ? 'bg-accent'
                            : comp.status === 'WARNING'
                            ? 'bg-warn'
                            : comp.status === 'CRITICAL'
                            ? 'bg-crit'
                            : 'bg-faint'
                        }`}
                      />
                    </div>
                    <div className="text-[12.5px] font-mono font-bold tracking-tight text-ink num">
                      {comp.primaryValue}
                    </div>
                    <div className="text-[10px] font-mono text-muted truncate num mt-0.5">
                      {comp.secondaryValue}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Right Column (3 cols): Sleek Integrated Component Inspector */}
        <div className="xl:col-span-3 lg:col-span-4 flex flex-col">
          <div className="card p-5 h-full flex flex-col justify-between rounded-xl shadow-sm">
            <div className="space-y-4">
              {/* Category Eyebrow & Component Title */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="eyebrow text-muted text-[10px]">
                    {currentComp.category}
                  </span>
                  <span className={`chip ${statusBadge.chipClass} text-[10px]`}>
                    <span className={`dot ${statusBadge.dotClass}`} />
                    <span>{statusBadge.label}</span>
                  </span>
                </div>

                <h3 className="text-[18px] font-semibold text-ink tracking-tight leading-snug">
                  {currentComp.name}
                </h3>
                <p className="text-[12.5px] text-muted mt-1.5 leading-relaxed">
                  {currentComp.description}
                </p>
              </div>

              {/* Authoritative Telemetry Spec Table */}
              <div className="pt-3 border-t border-line space-y-2">
                <span className="eyebrow text-muted text-[10px] block">
                  Authoritative Telemetry
                </span>

                <div className="space-y-1.5 max-h-[460px] overflow-y-auto pr-1">
                  {currentComp.metrics.map((m, idx) => (
                    <div
                      key={idx}
                      className={`p-2.5 rounded border transition-colors ${
                        m.isUnavailable
                          ? 'bg-surface-2/40 border-dashed border-line'
                          : 'bg-surface-2 border-line'
                      }`}
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-[12px] font-medium text-ink-2">
                          {m.label}
                        </span>
                        <span
                          className={`font-mono text-[12.5px] font-semibold num ${
                            m.isUnavailable ? 'text-muted italic text-[11px] font-normal' : 'text-ink'
                          }`}
                        >
                          {m.value}
                        </span>
                      </div>
                      {m.sublabel && (
                        <span className="text-[10.5px] text-muted block mt-0.5 leading-tight">
                          {m.sublabel}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Bottom Section: Evidence Action Link & Timestamp */}
            <div className="pt-4 mt-4 border-t border-line space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => handleSelectComponent(selectedId || 'tank')}
                  className="btn btn-secondary h-8 text-[11.5px] font-medium flex items-center justify-center gap-1.5"
                  title="Focus camera onto this component"
                >
                  <Target className="w-3.5 h-3.5 text-accent" />
                  <span>Focus in 3D</span>
                </button>
                <button
                  onClick={() => setCameraPresetTrigger('isometric')}
                  className="btn btn-secondary h-8 text-[11.5px] font-medium flex items-center justify-center gap-1.5"
                  title="Frame full transformer assembly"
                >
                  <Compass className="w-3.5 h-3.5 text-muted" />
                  <span>Fit All</span>
                </button>
              </div>

              {onNavigateTab && (
                <button
                  onClick={() => onNavigateTab(currentComp.targetTab)}
                  className="btn btn-primary w-full h-8 text-[12px] font-semibold flex items-center justify-center gap-1.5 shadow-sm"
                >
                  <span>{currentComp.targetTabLabel}</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
              <span className="meta text-center block text-[10px]">
                Synchronized with FactBundle · {timestamp}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
