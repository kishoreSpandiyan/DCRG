/**
 * DCRG Phase 8 - System Overview Bar (Section A).
 * Displays connection status, SIMULATION operating mode, active operator,
 * and quick-status tiles for Voice, Joystick, Sync, Fusion, Safety, and Simulation.
 */

import React, { useEffect, useState } from 'react';
import {
  Mic,
  Gamepad2,
  GitCommit,
  Cpu,
  Shield,
  Bot,
  User,
  Radio,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { fetchSystemOverview } from '../services/api';
import type { SystemOverviewPayload, AuthorizationState } from '../types';

interface SystemOverviewBarProps {
  onRefreshTrigger?: number;
}

export const SystemOverviewBar: React.FC<SystemOverviewBarProps> = ({ onRefreshTrigger }) => {
  const [overview, setOverview] = useState<SystemOverviewPayload | null>(null);

  useEffect(() => {
    fetchSystemOverview().then((data) => {
      if (data) setOverview(data);
    });
    const interval = window.setInterval(() => {
      fetchSystemOverview().then((data) => {
        if (data) setOverview(data);
      });
    }, 2000);
    return () => window.clearInterval(interval);
  }, [onRefreshTrigger]);

  const getStateBadgeStyle = (state?: AuthorizationState) => {
    switch (state) {
      case 'GREEN':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
      case 'YELLOW':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      case 'RED':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/40';
      case 'EMERGENCY':
        return 'bg-red-600/30 text-red-400 border-red-500 font-bold animate-pulse';
      default:
        return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg space-y-3 text-left">
      {/* Top Meta Line: Mode, Operator, Connection, Safety State */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800 pb-3">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-xs font-mono">
            <Radio className="w-3.5 h-3.5 text-cyan-400 animate-pulse" />
            <span className="text-slate-400">MODE:</span>
            <span className="text-cyan-300 font-bold tracking-wide">SIMULATION</span>
          </div>

          <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-xs font-mono">
            <User className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">OPERATOR:</span>
            <span className="text-slate-200 font-semibold">{overview?.active_operator || 'OP-PRIMARY'}</span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-xs font-mono">
            {overview?.backend_connected ? (
              <>
                <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                <span className="text-emerald-400 font-medium">SYSTEM ONLINE</span>
              </>
            ) : (
              <>
                <WifiOff className="w-3.5 h-3.5 text-rose-400" />
                <span className="text-rose-400 font-medium">DISCONNECTED</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-mono text-slate-400">Safety State:</span>
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold border tracking-wider uppercase font-mono ${getStateBadgeStyle(
              overview?.active_safety_state
            )}`}
          >
            {overview?.active_safety_state || 'GREEN'}
          </span>
        </div>
      </div>

      {/* Subsystem Telemetry Quick-Matrix */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 text-xs font-mono">
        {/* 1. Voice Subsystem */}
        <div className="p-2.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="flex items-center gap-1.5">
              <Mic className="w-3.5 h-3.5 text-purple-400" /> Voice
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                overview?.voice.status === 'CONNECTED' ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
          </div>
          <div className="text-slate-200 font-semibold truncate">
            {overview?.voice.last_command || 'IDLE'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5 truncate">
            {overview?.voice.model || 'tiny.en'} ({overview?.voice.status || 'MUTED'})
          </div>
        </div>

        {/* 2. Joystick Subsystem */}
        <div className="p-2.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="flex items-center gap-1.5">
              <Gamepad2 className="w-3.5 h-3.5 text-blue-400" /> Joystick
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                overview?.joystick.connection_status === 'CONNECTED' ? 'bg-emerald-400' : 'bg-cyan-400'
              }`}
            />
          </div>
          <div className="text-slate-200 font-semibold truncate">
            {overview?.joystick.direction || 'CENTER'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5 truncate">
            {overview?.joystick.mode === 'REAL_HARDWARE' ? 'USB Hardware' : 'Virtual Stick'}
          </div>
        </div>

        {/* 3. Synchronization */}
        <div className="p-2.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="flex items-center gap-1.5">
              <GitCommit className="w-3.5 h-3.5 text-amber-400" /> Sync Window
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
          </div>
          <div className="text-slate-200 font-semibold">
            {overview?.synchronization.sync_window_ms || 150} ms
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            {overview?.synchronization.total_synchronized || 0} paired events
          </div>
        </div>

        {/* 4. Fusion Engine (CRS) */}
        <div className="p-2.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="flex items-center gap-1.5">
              <Cpu className="w-3.5 h-3.5 text-emerald-400" /> CRS Engine
            </span>
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
          </div>
          <div className="text-emerald-400 font-bold">
            {overview?.fusion.last_crs !== null && overview?.fusion.last_crs !== undefined
              ? `${overview.fusion.last_crs.toFixed(1)} / 100`
              : 'N/A'}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Avg: {overview?.fusion.average_crs.toFixed(1) || '0.0'} (Eval: {overview?.fusion.total_evaluations || 0})
          </div>
        </div>

        {/* 5. Safety Authorization */}
        <div className="p-2.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-cyan-400" /> Safety Gate
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                overview?.safety.is_emergency_latched
                  ? 'bg-red-500 animate-ping'
                  : overview?.safety.state === 'GREEN'
                  ? 'bg-emerald-400'
                  : 'bg-amber-400'
              }`}
            />
          </div>
          <div className="text-slate-200 font-semibold truncate">
            {overview?.safety.is_emergency_latched ? 'E-STOP LATCH' : `${overview?.safety.total_authorized || 0} Authorized`}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Pending: {overview?.safety.pending_confirmations || 0} holds
          </div>
        </div>

        {/* 6. Robot Simulator */}
        <div className="p-2.5 bg-slate-950/70 rounded-lg border border-slate-800/80 flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 mb-1">
            <span className="flex items-center gap-1.5">
              <Bot className="w-3.5 h-3.5 text-indigo-400" /> 2D Vehicle
            </span>
            <span
              className={`w-2 h-2 rounded-full ${
                overview?.simulation.is_collision
                  ? 'bg-rose-500'
                  : overview?.simulation.is_paused
                  ? 'bg-amber-400'
                  : 'bg-emerald-400'
              }`}
            />
          </div>
          <div className="text-slate-200 font-semibold truncate">
            ({overview?.simulation.x.toFixed(1) || '0.0'}, {overview?.simulation.y.toFixed(1) || '0.0'})
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">
            Cmd: {overview?.simulation.active_command || 'STOP'} ({overview?.simulation.speed_multiplier || 1}x)
          </div>
        </div>
      </div>
    </div>
  );
};
