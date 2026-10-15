import React from 'react';
import {
  RefreshCw,
  Moon,
  Sun,
  LayoutGrid,
  Thermometer,
  ScanSearch,
  Wrench,
  Zap,
  FileText,
  Box,
  History,
  PanelLeftClose,
} from 'lucide-react';

interface NavbarProps {
  isBackendHealthy: boolean;
  activeTab: string;
  onTabChange: (tab: string) => void;
  onRefresh: () => void;
  isRefreshing: boolean;
  theme?: 'light' | 'dark';
  onToggleTheme?: () => void;
  siteLabel?: string;
  isSidebarOpen?: boolean;
  onToggleSidebar?: () => void;
}

const BrandMark: React.FC = () => (
  <svg viewBox="0 0 24 24" className="w-6 h-6 text-ink" fill="none" aria-hidden="true">
    <path d="M3 12h4l2.5-6 5 12 2.5-6h4" stroke="currentColor" strokeWidth="2.4" strokeLinecap="square" strokeLinejoin="miter" />
  </svg>
);

export const Navbar: React.FC<NavbarProps> = ({
  isBackendHealthy,
  activeTab,
  onTabChange,
  onRefresh,
  isRefreshing,
  theme = 'light',
  onToggleTheme,
  siteLabel = '',
  isSidebarOpen = true,
  onToggleSidebar,
}) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutGrid },
    { id: 'twin-analysis', label: 'Thermal & What-If', icon: Thermometer },
    { id: 'anomalies', label: 'Anomalies & Evidence', icon: ScanSearch },
    { id: 'maintenance', label: 'Maintenance Advisories', icon: Wrench },
    { id: 'telemetry', label: 'Electrical Telemetry', icon: Zap },
    { id: 'historical', label: 'Historical & Reports', icon: History },
    { id: 'model-card', label: 'Model Card & Specs', icon: FileText },
    { id: 'twin-3d', label: '3D Component View', icon: Box },
  ];


  const statusPill = (
    <div className="flex items-center gap-2 text-[12px] font-medium text-ink-2 tracking-[-0.005em]">
      <span className="relative flex w-2 h-2">
        <span className={`absolute inset-0 rounded-full ${isBackendHealthy ? 'bg-ok/25' : 'bg-warn/25'} scale-[1.9]`} />
        <span className={`relative dot w-2 h-2 ${isBackendHealthy ? 'bg-ok' : 'bg-warn'}`} />
      </span>
      <span>{isBackendHealthy ? 'Twin Online' : 'Degraded'}</span>
    </div>
  );

  const refreshButton = (
    <button
      onClick={onRefresh}
      disabled={isRefreshing}
      title="Refresh Digital Twin State"
      className="icon-btn bg-transparent hover:bg-surface"
    >
      <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-accent' : ''}`} strokeWidth={1.75} />
    </button>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={`hidden lg:flex fixed inset-y-0 left-0 z-40 w-60 flex-col bg-sidebar border-r border-line transition-transform duration-300 ease-in-out ${
          isSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand & Sidebar Close Toggle */}
        <div className="px-5 pt-6 pb-6 select-none border-b border-line/60">
          <div className="flex items-center justify-between">
            <div
              onClick={() => onTabChange('overview')}
              className="flex items-center gap-2.5 cursor-pointer"
              title="Go to Overview"
            >
              <BrandMark />
              <span className="font-display text-[23px] font-semibold tracking-[-0.01em] text-ink leading-none">
                GridPulse
              </span>
            </div>
            {onToggleSidebar && (
              <button
                onClick={onToggleSidebar}
                className="icon-btn w-8 h-8 rounded-lg hover:bg-surface text-muted hover:text-ink transition-colors flex items-center justify-center border border-transparent hover:border-line"
                title="Close sidebar (Collapse)"
                id="btn-close-sidebar"
                aria-label="Close sidebar"
              >
                <PanelLeftClose className="w-4 h-4" />
              </button>
            )}
          </div>
          <p className="mt-2.5 text-[10.5px] font-medium text-muted leading-[1.5] tracking-[-0.01em]">
            Distribution Transformer Digital Twin
            <br />
            <span className="text-muted/80">{siteLabel}</span>
          </p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 space-y-px overflow-y-auto">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                aria-current={isActive ? 'page' : undefined}
                className={`relative w-full h-10 px-3 flex items-center gap-3 rounded text-[13.5px] tracking-[-0.01em] text-left transition-colors ${
                  isActive
                    ? 'bg-accent-soft text-ink font-semibold ring-1 ring-accent/15'
                    : 'text-ink-2 font-medium hover:text-ink hover:bg-ink/[0.035]'
                }`}
              >
                {isActive && (
                  <span className="absolute left-0 top-2.5 bottom-2.5 w-[2px] rounded-full bg-accent" />
                )}
                <Icon
                  className={`w-[17px] h-[17px] flex-shrink-0 ${isActive ? 'text-accent' : 'text-muted'}`}
                  strokeWidth={1.6}
                />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Footer: status, refresh, theme */}
        <div className="mx-3 mb-4 p-3 rounded-card border border-line bg-canvas/60 space-y-3">
          <div className="flex items-center justify-between pl-1">
            {statusPill}
            {refreshButton}
          </div>
          {onToggleTheme && (
            <div className="grid grid-cols-2 p-[3px] rounded-full bg-ink/[0.05] border border-line">
              <button
                onClick={() => theme === 'dark' && onToggleTheme()}
                title="Switch to Light Mode"
                className={`h-7 rounded-full flex items-center justify-center transition-colors ${
                  theme === 'light' ? 'bg-surface text-ink shadow-subtle ring-1 ring-line' : 'text-muted hover:text-ink'
                }`}
              >
                <Sun className="w-[15px] h-[15px]" strokeWidth={1.75} />
              </button>
              <button
                onClick={() => theme === 'light' && onToggleTheme()}
                title="Switch to Dark Mode"
                className={`h-7 rounded-full flex items-center justify-center transition-colors ${
                  theme === 'dark' ? 'bg-surface text-ink shadow-subtle ring-1 ring-line' : 'text-muted hover:text-ink'
                }`}
              >
                <Moon className="w-[15px] h-[15px]" strokeWidth={1.75} />
              </button>
            </div>
          )}
        </div>
      </aside>


      {/* Tablet / mobile top bar */}
      <header className="lg:hidden sticky top-0 z-40 bg-sidebar/95 backdrop-blur border-b border-line transition-colors">
        <div className="px-4 sm:px-6 h-14 flex items-center justify-between gap-3">
          <div
            onClick={() => onTabChange('overview')}
            className="flex items-center gap-2 cursor-pointer select-none min-w-0"
          >
            <BrandMark />
            <span className="font-display text-[19px] font-semibold tracking-[-0.01em] text-ink">GridPulse</span>
            <span className="hidden sm:inline text-[11px] text-muted truncate">
              · {siteLabel}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="hidden sm:flex">{statusPill}</div>
            {onToggleTheme && (
              <button
                onClick={onToggleTheme}
                title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
                className="icon-btn"
              >
                {theme === 'dark' ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
              </button>
            )}
            {refreshButton}
          </div>
        </div>

        <nav className="px-2 sm:px-4 flex items-center gap-1 overflow-x-auto border-t border-line">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={`px-2.5 py-2.5 text-[12px] whitespace-nowrap border-b-2 -mb-px transition-colors ${
                  isActive
                    ? 'border-accent text-ink font-semibold'
                    : 'border-transparent text-muted hover:text-ink'
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </nav>
      </header>
    </>
  );
};
