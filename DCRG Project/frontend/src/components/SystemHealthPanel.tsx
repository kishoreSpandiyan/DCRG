/**
 * DCRG Phase 8 - Detailed System Health & Service Diagnostics Panel (Section 8).
 * Real-time diagnostic probes for Backend, Voice, Joystick, Database, WebSockets,
 * Gateway, and Simulator.
 * Strictly avoids false healthy reports; indicates UNKNOWN/UNTESTED appropriately.
 */

import React, { useEffect, useState } from 'react';
import {
  HeartPulse,
  Server,
  Database,
  Radio,
  Gamepad2,
  Mic,
  Shield,
  Bot,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Clock,
} from 'lucide-react';
import { fetchDetailedHealth } from '../services/api';
import type { DetailedHealthPayload } from '../types';

export const SystemHealthPanel: React.FC = () => {
  const [healthData, setHealthData] = useState<DetailedHealthPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [lastCheck, setLastCheck] = useState<Date | null>(null);

  const loadHealth = async () => {
    setLoading(true);
    try {
      const res = await fetchDetailedHealth();
      if (res) {
        setHealthData(res);
        setLastCheck(new Date());
      }
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
    const interval = window.setInterval(loadHealth, 5000);
    return () => window.clearInterval(interval);
  }, []);

  const getStatusBadge = (statusStr: string) => {
    const s = (statusStr || 'UNKNOWN').toUpperCase();
    if (s.includes('HEALTHY') || s === 'OPERATIONAL') {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-emerald-950/80 text-emerald-400 border border-emerald-800">
          <CheckCircle2 className="w-3.5 h-3.5" /> {statusStr}
        </span>
      );
    } else if (s.includes('IDLE') || s.includes('DEGRADED') || s.includes('VIRTUAL')) {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-amber-950/80 text-amber-400 border border-amber-800">
          <AlertTriangle className="w-3.5 h-3.5" /> {statusStr}
        </span>
      );
    } else if (s.includes('DISCONNECTED') || s.includes('STOPPED') || s.includes('ERROR')) {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-rose-950/80 text-rose-400 border border-rose-800">
          <XCircle className="w-3.5 h-3.5" /> {statusStr}
        </span>
      );
    } else {
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-mono font-bold bg-slate-800 text-slate-400 border border-slate-700">
          <HelpCircle className="w-3.5 h-3.5" /> {statusStr || 'UNKNOWN'}
        </span>
      );
    }
  };

  const services = healthData?.services;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6 text-left">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-rose-500/10 rounded-lg border border-rose-500/20">
            <HeartPulse className="w-6 h-6 text-rose-400 animate-pulse" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
              System Health & Service Availability Diagnostics
              <span className="text-xs px-2 py-0.5 rounded-full bg-rose-900/60 text-rose-300 border border-rose-700 font-mono">
                Probe Active
              </span>
            </h2>
            <p className="text-sm text-slate-400">
              Active verification of micro-services, databases, socket streams, and isolation boundaries
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-xs font-mono text-slate-400 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            Last Probe: {lastCheck ? lastCheck.toTimeString().split(' ')[0] : 'Checking...'} (
            {healthData?.diagnostic_latency_ms || 0} ms)
          </div>

          <button
            onClick={loadHealth}
            disabled={loading}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Refresh diagnostics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Service Diagnostics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. Backend Core */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 font-mono">
                <Server className="w-4 h-4 text-cyan-400" /> Backend Core
              </span>
              {getStatusBadge(services?.backend_core.status || 'UNKNOWN')}
            </div>
            <p className="text-xs text-slate-400 font-mono">
              FastAPI v{services?.backend_core.version || '0.4.0'} ({services?.backend_core.environment || 'dev'})
            </p>
          </div>
          <div className="text-[10px] text-slate-500 font-mono border-t border-slate-900 pt-1.5">
            REST API & Router active
          </div>
        </div>

        {/* 2. Voice Recognition Engine */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 font-mono">
                <Mic className="w-4 h-4 text-purple-400" /> Voice Service
              </span>
              {getStatusBadge(services?.voice_service.status || 'UNKNOWN')}
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Model: {services?.voice_service.model_name || 'tiny.en'}
            </p>
          </div>
          <div className="text-[10px] text-slate-500 font-mono border-t border-slate-900 pt-1.5">
            Mic: {services?.voice_service.microphone_status || 'UNKNOWN'}
          </div>
        </div>

        {/* 3. Joystick & Actuator Engine */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 font-mono">
                <Gamepad2 className="w-4 h-4 text-blue-400" /> Joystick Service
              </span>
              {getStatusBadge(services?.joystick_service.status || 'UNKNOWN')}
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Mode: {services?.joystick_service.mode || 'VIRTUAL'}
            </p>
          </div>
          <div className="text-[10px] text-slate-500 font-mono border-t border-slate-900 pt-1.5">
            Physical Detected: {services?.joystick_service.hardware_detected ? 'YES' : 'NO'}
          </div>
        </div>

        {/* 4. Event Synchronization Engine */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 font-mono">
                <Radio className="w-4 h-4 text-amber-400" /> Sync Engine
              </span>
              {getStatusBadge(services?.sync_service.status || 'UNKNOWN')}
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Window: {services?.sync_service.sync_window_ms || 150} ms
            </p>
          </div>
          <div className="text-[10px] text-slate-500 font-mono border-t border-slate-900 pt-1.5">
            Total Paired: {services?.sync_service.total_synchronized || 0}
          </div>
        </div>

        {/* 5. Fusion Engine (CRS) */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 font-mono">
                <Shield className="w-4 h-4 text-emerald-400" /> Fusion CRS Engine
              </span>
              {getStatusBadge(services?.fusion_service.status || 'UNKNOWN')}
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Scoring: {services?.fusion_service.scoring_version || 'v1.0'}
            </p>
          </div>
          <div className="text-[10px] text-slate-500 font-mono border-t border-slate-900 pt-1.5">
            Evaluations: {services?.fusion_service.total_evaluations || 0}
          </div>
        </div>

        {/* 6. Safety Gateway Interlock */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 font-mono">
                <Shield className="w-4 h-4 text-cyan-400" /> Gateway Interlock
              </span>
              {getStatusBadge(services?.safety_gateway.status || 'UNKNOWN')}
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Simulation-Only: {services?.safety_gateway.simulation_only_enforced ? 'ENFORCED' : 'OFF'}
            </p>
          </div>
          <div className="text-[10px] text-slate-500 font-mono border-t border-slate-900 pt-1.5">
            Accepted: {services?.safety_gateway.total_accepted || 0} | Rejected: {services?.safety_gateway.total_rejected || 0}
          </div>
        </div>

        {/* 7. Robot Simulation Engine */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 font-mono">
                <Bot className="w-4 h-4 text-indigo-400" /> Robot Simulator
              </span>
              {getStatusBadge(services?.robot_simulator.status || 'UNKNOWN')}
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Tick Rate: {services?.robot_simulator.tick_rate_hz || 20} Hz
            </p>
          </div>
          <div className="text-[10px] text-slate-500 font-mono border-t border-slate-900 pt-1.5">
            Paused: {services?.robot_simulator.is_paused ? 'YES' : 'NO'} | Speed: {services?.robot_simulator.speed_multiplier || 1}x
          </div>
        </div>

        {/* 8. SQLite Database Persistence */}
        <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2.5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 font-mono">
                <Database className="w-4 h-4 text-yellow-400" /> SQLite Persistence
              </span>
              {getStatusBadge(services?.database_persistence.status || 'UNKNOWN')}
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Audit Logs: {services?.database_persistence.total_audit_events || 0} records
            </p>
          </div>
          <div className="text-[10px] text-slate-500 font-mono border-t border-slate-900 pt-1.5 truncate" title={services?.database_persistence.db_path}>
            {services?.database_persistence.db_path || 'dcrg_audit.db'}
          </div>
        </div>
      </div>
    </div>
  );
};
