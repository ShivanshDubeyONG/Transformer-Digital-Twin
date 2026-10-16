import React from 'react';
import { Cpu } from 'lucide-react';
import { API_BASE, ModelCardData } from '../../services/api';
import { UIHonestyBadge } from '../common/UIHonestyBadge';

const fmt = (v: number | null | undefined, digits: number): string => (v == null ? '—' : v.toFixed(digits));


interface DataModelCardViewProps {
  modelCard: ModelCardData | null;
}

export const DataModelCardView: React.FC<DataModelCardViewProps> = ({ modelCard }) => {
  if (!modelCard) {
    return (
      <div className="card p-6 text-sm text-muted">
        Model card unavailable: the backend has not returned a model artifact for this asset, so no model metadata is shown.
      </div>
    );
  }
  const card = modelCard;

  const isPromoted = card.promotion.status === 'PROMOTED';

  const parameterCells = [
    { label: 'Time Constant (τ)', value: fmt(card.parameters?.tau_hours, 2), unit: 'hours', note: 'Estimated thermal inertia' },
    { label: 'Ambient Offset (β₀)', value: fmt(card.parameters?.beta_0, 4), unit: '°C', note: 'Steady-state no-load temperature rise' },
    { label: 'Load Coefficient (β₁)', value: fmt(card.parameters?.beta_1, 4), unit: '°C', note: 'Full-load squared heating coefficient' },
  ];

  const exports = [
    {
      href: `${API_BASE}/v1/reports/summary.pdf`,
      title: 'Export PDF',
      tag: 'PDF',
      desc: 'Audit / historical condition report with frozen provenance and qualification gates.',
      cta: 'Download PDF Report →',
    },
    {
      href: `${API_BASE}/v1/reports/summary.csv`,
      title: 'Export CSV',
      tag: 'CSV',
      desc: 'Tabular metrics and electrical features export for external statistical audit.',
      cta: 'Download CSV Data →',
    },
    {
      href: `${API_BASE}/v1/reports/summary.json`,
      title: 'Export JSON',
      tag: 'JSON',
      desc: 'Complete machine-readable FactBundle state vector snapshot with SHA-256 hashes.',
      cta: 'Download JSON FactBundle →',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="page-header">
        <div>
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <span className="eyebrow">Model Card & Audit Specification</span>
            <span className={`chip font-mono ${isPromoted ? 'chip-ok' : 'chip-warn'}`}>
              {card.promotion.status} · {isPromoted ? 'Qualified model' : 'Descriptive Shadow Mode'}
            </span>
          </div>
          <h1 className="page-title">Grey-Box Thermal Model Card</h1>
          <p className="text-[13px] text-muted mt-2.5 max-w-2xl">
            Physics-grounded first-order differential equation parameters, empirical calibration results, and qualification boundaries.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <UIHonestyBadge type="DEMO_DEFAULT" />
          <UIHonestyBadge type="relative_load_index" />
        </div>
      </div>

      {/* 1. Model Formulation & Calibrated Parameters */}
      <div>
        <div className="flex items-center gap-2.5 mb-3">
          <Cpu className="w-[18px] h-[18px] text-muted" strokeWidth={1.75} />
          <h2 className="section-title">Thermal Differential Equation & Parameter Values</h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-px bg-line border border-line rounded-card overflow-hidden">
          <div className="lg:col-span-5 bg-inverse text-on-inverse p-6 flex flex-col justify-between">
            <div>
              <span className="text-[11px] font-semibold uppercase tracking-eyebrow text-on-inverse/70 block pb-3 border-b border-on-inverse/15">
                Differential Equation Formulation
              </span>
              <div className="font-mono text-[15px] mt-5 text-on-inverse">
                dθ_o / dt = (1 / τ) · (β₀ + β₁ · u² - θ_o)
              </div>
            </div>
            <p className="text-[11px] text-on-inverse/65 mt-6 leading-relaxed">
              Where <span className="font-mono text-on-inverse">θ_o</span> is top-oil temperature, <span className="font-mono text-on-inverse">u = {card.selected_load_driver === 'apparent_power_kva' ? 'S / S_ref' : 'I_rms / I_ref'}</span> is relative load, <span className="font-mono text-on-inverse">τ</span> is the thermal time constant, <span className="font-mono text-on-inverse">β₀</span> is the ambient baseline offset, and <span className="font-mono text-on-inverse">β₁</span> is the load heating coefficient.
            </p>
          </div>

          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-3 gap-px bg-line">
            {parameterCells.map((p) => (
              <div key={p.label} className="bg-surface p-5 flex flex-col">
                <span className="eyebrow block pb-3 border-b border-line">{p.label}</span>
                <div className="mt-4 flex items-baseline gap-1.5">
                  <span className="metric-value text-[32px]">{p.value}</span>
                  <span className="metric-unit">{p.unit}</span>
                </div>
                <span className="text-[11px] text-muted mt-auto pt-4 block">{p.note}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Calibration & Test Partition Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h2 className="section-title mb-3">Test Partition Accuracy</h2>
          <dl className="card px-5 py-1.5">
            <div className="kv">
              <dt>Mean Absolute Error (MAE)</dt>
              <dd className="font-mono font-semibold text-ink">{fmt(card.test_metrics?.mae_degc, 2)} °C</dd>
            </div>
            <div className="kv">
              <dt>Root Mean Square Error (RMSE)</dt>
              <dd className="font-mono font-semibold text-ink">{fmt(card.test_metrics?.rmse_degc, 2)} °C</dd>
            </div>
            <div className="kv">
              <dt title="Empirical marginal interval coverage on test partition; not simultaneous continuous-path coverage">
                90% Marginal Step Coverage (Test)
              </dt>
              <dd className="font-mono font-semibold text-ink">{fmt(card.test_metrics?.marginal_coverage_90_pct, 1)}%</dd>
            </div>
            <div className="kv">
              <dt>Training Samples</dt>
              <dd className="font-mono text-ink-2 text-right">{(card.identifiability?.fit_samples_count?.toLocaleString() ?? '—')} frames ({fmt(card.identifiability?.fit_span_days, 0)} days)</dd>
            </div>
          </dl>
        </div>

        <div>
          <h2 className="section-title mb-3">Qualification & Safety Governance</h2>
          <dl className="card px-5 py-1.5">
            <div className="kv">
              <dt>Parameter Interpretability</dt>
              <dd className="font-mono text-ink-2">{card.qualification?.parameter_interpretability}</dd>
            </div>
            <div className="kv">
              <dt>Forecast Qualification</dt>
              <dd className="font-mono text-ink-2">{card.qualification?.forecast_qualification}</dd>
            </div>
            <div className="kv">
              <dt>Scenario Projection</dt>
              <dd className="font-mono text-ink-2">{card.qualification?.scenario_qualification}</dd>
            </div>
            <div className="kv">
              <dt>Promotion Status</dt>
              <dd className="font-mono font-semibold text-warn">{card.promotion.status}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* 3. Discoverable Audit Reports & Data Export */}
      <div>
        <div className="mb-3">
          <h2 className="section-title">Audit Reports & Authoritative Data Export</h2>
          <p className="text-xs text-muted mt-1">
            Download frozen engineering records directly from the digital twin report pipeline.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-line border border-line rounded-card overflow-hidden">
          {exports.map((x) => (
            <a
              key={x.href}
              href={x.href}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-surface hover:bg-surface-2 p-5 transition-colors flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-center justify-between pb-3 border-b border-line mb-3">
                  <span className="card-title">{x.title}</span>
                  <span className="chip chip-neutral font-mono">{x.tag}</span>
                </div>
                <p className="text-[11.5px] text-muted leading-relaxed">{x.desc}</p>
              </div>
              <span className="text-xs font-medium text-accent group-hover:underline underline-offset-2 mt-5 block">
                {x.cta}
              </span>
            </a>
          ))}
        </div>
      </div>
    </div>
  );
};
