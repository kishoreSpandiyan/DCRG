/**
 * DCRG Phase 8 - Complete Unified Command & Control Dashboard.
 * Integrates all subsystems from Phase 1 through Phase 7 into a modern,
 * responsive industrial command-center with tabbed navigation.
 */

import React, { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { SystemOverviewBar } from '../components/SystemOverviewBar';
import { JoystickDashboardPanel } from '../joystick/JoystickDashboardPanel';
import { VoiceDashboardPanel } from '../voice/VoiceDashboardPanel';
import { SynchronizationDashboardPanel } from '../sync/SynchronizationDashboardPanel';
import { FusionDashboardPanel } from '../fusion/FusionDashboardPanel';
import { SafetyDashboardPanel } from '../safety/SafetyDashboardPanel';
import { RobotSimulationPanel } from '../simulation/RobotSimulationPanel';
import { AuditLogsPanel } from '../components/AuditLogsPanel';
import { ConfigurationPanel } from '../components/ConfigurationPanel';
import { SystemHealthPanel } from '../components/SystemHealthPanel';
import { LiveEventTimeline } from '../components/LiveEventTimeline';
import { fetchSystemHealth, triggerEmergencyStop } from '../services/api';
import type { SystemStatusPayload } from '../types';
import {
  LayoutDashboard,
  Radio,
  Cpu,
  Bot,
  FileText,
  Sliders,
  HeartPulse,
  Terminal,
  AlertOctagon,
} from 'lucide-react';

type TabKey =
  | 'command_center'
  | 'monitors'
  | 'fusion_safety'
  | 'simulation'
  | 'logs'
  | 'config'
  | 'health';

export const MainPage: React.FC = () => {
  const [health, setHealth] = useState<SystemStatusPayload | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('command_center');

  useEffect(() => {
    fetchSystemHealth().then((data) => setHealth(data));
    const interval = window.setInterval(() => {
      fetchSystemHealth().then((data) => setHealth(data));
    }, 3000);
    return () => window.clearInterval(interval);
  }, []);

  const handleGlobalEStop = async () => {
    try {
      await triggerEmergencyStop('SOFTWARE_UI', 'Emergency Stop from Global Dashboard Bar');
    } catch {
      // Ignored
    }
  };

  const navItems = [
    { key: 'command_center', label: 'Command Center', icon: LayoutDashboard },
    { key: 'monitors', label: 'Multi-Modal Monitors', icon: Radio },
    { key: 'fusion_safety', label: 'Fusion & Safety', icon: Cpu },
    { key: 'simulation', label: 'Robot Simulation', icon: Bot },
    { key: 'logs', label: 'Audit Logs', icon: FileText },
    { key: 'config', label: 'Configuration', icon: Sliders },
    { key: 'health', label: 'System Health', icon: HeartPulse },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      <Header
        backendConnected={health?.backendConnected ?? false}
        phase={health?.phase ?? 'Phase 8 – Complete Dashboard & End-to-End Integration'}
      />

      {/* Industrial Sub-Header Navigation Bar */}
      <div className="bg-slate-900 border-b border-slate-800 px-6 py-2.5">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
          {/* Navigation Tabs */}
          <nav className="flex items-center space-x-1.5 overflow-x-auto py-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.key;
              return (
                <button
                  key={item.key}
                  onClick={() => setActiveTab(item.key as TabKey)}
                  className={`flex items-center space-x-2 px-3.5 py-1.5 rounded-lg text-xs font-mono font-medium transition whitespace-nowrap ${
                    isActive
                      ? 'bg-cyan-600 text-white shadow-md shadow-cyan-900/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/80'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Quick Global Action: Emergency Stop */}
          <button
            onClick={handleGlobalEStop}
            className="flex items-center space-x-1.5 px-3.5 py-1 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-mono font-bold uppercase tracking-wider transition shadow-lg shadow-rose-900/30"
          >
            <AlertOctagon className="w-4 h-4" />
            <span>GLOBAL E-STOP</span>
          </button>
        </div>
      </div>

      <main className="flex-1 p-6 space-y-6 max-w-7xl mx-auto w-full">
        {/* System Overview Bar (Always visible in Command Center, or globally) */}
        <SystemOverviewBar />

        {/* Tab 1: Command Center (Central Mission View) */}
        {activeTab === 'command_center' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              <div className="lg:col-span-8">
                <RobotSimulationPanel />
              </div>
              <div className="lg:col-span-4 space-y-6">
                <SafetyDashboardPanel />
                <LiveEventTimeline />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Multi-Modal Monitors (Voice, Joystick, Sync) */}
        {activeTab === 'monitors' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <VoiceDashboardPanel />
              <JoystickDashboardPanel />
            </div>
            <SynchronizationDashboardPanel />
          </div>
        )}

        {/* Tab 3: Fusion & Safety Gate (CRS Breakdown & Rules) */}
        {activeTab === 'fusion_safety' && (
          <div className="space-y-6">
            <FusionDashboardPanel />
            <SafetyDashboardPanel />
          </div>
        )}

        {/* Tab 4: Robot Simulation (Dedicated 2D Testbed) */}
        {activeTab === 'simulation' && (
          <div className="space-y-6">
            <RobotSimulationPanel />
          </div>
        )}

        {/* Tab 5: Forensic Audit Logs (SQLite History & Export) */}
        {activeTab === 'logs' && (
          <div className="space-y-6">
            <AuditLogsPanel />
          </div>
        )}

        {/* Tab 6: Configuration Panel (Settings & Invariant Checks) */}
        {activeTab === 'config' && (
          <div className="space-y-6">
            <ConfigurationPanel />
          </div>
        )}

        {/* Tab 7: System Health (Detailed Diagnostics Probe) */}
        {activeTab === 'health' && (
          <div className="space-y-6">
            <SystemHealthPanel />
          </div>
        )}

        {/* Console / Terminal Status Bar */}
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl max-w-7xl mx-auto text-left">
          <div className="flex items-center space-x-2 mb-2 text-slate-400">
            <Terminal className="w-4 h-4 text-slate-400" />
            <span className="text-xs font-mono uppercase tracking-wider">System Integration Status</span>
          </div>
          <pre className="text-xs font-mono bg-slate-950 p-3 rounded border border-slate-800/80 text-emerald-400 overflow-x-auto">
            {JSON.stringify(
              {
                system: 'Dynamic Command Reliability Graph (DCRG)',
                phase: 'Phase 8 – Complete Dashboard & End-to-End Integration',
                activeTab,
                backendStatus: health?.backendConnected ? 'ONLINE' : 'OFFLINE_OR_PENDING_BOOT',
                activeSafetyState: health?.activeSafetyState ?? 'INITIALIZING',
                pipeline: 'VOICE + JOYSTICK -> SYNC -> FUSION (CRS) -> SAFETY GATE -> SIMULATION GATEWAY -> 2D SIMULATOR',
                stack: {
                  backend: 'FastAPI + Python 3.14 + SQLite Audit Logger + Faster-Whisper + Librosa + Pygame-CE',
                  frontend: 'React 19 + TypeScript + Vite + Tailwind CSS + Lucide React',
                  database: 'SQLite (dcrg_audit.db) in WAL mode',
                  safety: 'Tiered Rule Engine + Cryptographic Gateway Tokens + Emergency Stop Priority',
                },
              },
              null,
              2
            )}
          </pre>
        </div>
      </main>
    </div>
  );
};
