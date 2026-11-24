/**
 * DCRG Phase 8 - Live CRS Real-Time Monitor Banner.
 * Displays real-time Command Reliability Score (CRS) inside the Multi-Modal Monitors tab
 * so operators never need to switch tabs to be aware of reliability and safety authorization.
 */

import React from 'react';
import {
  Gauge,
  ShieldAlert,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { useFusionStream } from '../hooks/useFusionStream';
import type { AnalyticalFinding } from '../types';

export const CRSMonitorBanner: React.FC = () => {
  const { latestFusion, isWsConnected } = useFusionStream();

  const crs = latestFusion?.CRS ?? null;
  const isVeto = latestFusion?.contradiction_detected ?? false;
  const finding = latestFusion?.analytical_finding;
  const recState = latestFusion?.recommended_state;

  const getCRSColor = (score: number | null, veto: boolean) => {
    if (score === null) return 'text-slate-400 border-slate-700 bg-slate-900/60';
    if (veto || score < 50) return 'text-rose-400 border-rose-500/60 bg-rose-950/40';
    if (score < 85) return 'text-amber-400 border-amber-500/60 bg-amber-950/40';
    return 'text-emerald-400 border-emerald-500/60 bg-emerald-950/40';
  };

  const getTargetBadgeStyle = (state?: string | null) => {
    switch (state) {
      case 'GREEN':
        return 'bg-emerald-950 text-emerald-300 border-emerald-600';
      case 'YELLOW':
        return 'bg-amber-950 text-amber-300 border-amber-600';
      case 'RED':
        return 'bg-rose-950 text-rose-300 border-rose-600';
      case 'EMERGENCY':
        return 'bg-red-950 text-red-200 border-red-500 animate-pulse';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-600';
    }
  };

  const renderFindingBadge = (f?: AnalyticalFinding) => {
    switch (f) {
      case 'AGREEMENT':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-emerald-900/60 text-emerald-300 border border-emerald-700">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span>AGREEMENT</span>
          </span>
        );
      case 'CONTRADICTION':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-rose-900/80 text-rose-300 border border-rose-600 animate-pulse">
            <XCircle className="w-3 h-3 text-rose-400" />
            <span>CONTRADICTION VETO</span>
          </span>
        );
      case 'CONTEXT_VIOLATION':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-amber-900/60 text-amber-300 border border-amber-700">
            <AlertTriangle className="w-3 h-3 text-amber-400" />
            <span>CONTEXT_VIOLATION</span>
          </span>
        );
      case 'NEUTRAL_JOYSTICK':
        return (
          <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-cyan-900/50 text-cyan-300 border border-cyan-700">
            NEUTRAL_JOYSTICK
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            {f || 'AWAITING MULTI-MODAL INPUT'}
          </span>
        );
    }
  };

  return (
    <div className="bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-indigo-900/40 rounded-2xl p-5 shadow-2xl space-y-4 text-left">
      {/* Top Header: Title & Real-time Live Connection */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-800/80 gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/15 border border-indigo-500/30 text-indigo-400">
            <Gauge className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h2 className="text-lg font-bold text-slate-100 tracking-wide m-0">
                Command Reliability Score (CRS) Live Monitor
              </h2>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-700">
                Phase 5 Real-Time
              </span>
            </div>
            <p className="text-xs text-slate-400 m-0">
              Live multi-modal agreement evaluation • Active concurrently with Voice & Actuator telemetry
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2.5">
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-slate-950/70 border border-slate-800 text-xs font-mono">
            <span className={`w-2 h-2 rounded-full ${isWsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
            <span className="text-slate-300">{isWsConnected ? 'CRS Live Stream' : 'REST Polling'}</span>
          </div>
          {renderFindingBadge(finding)}
        </div>
      </div>

      {/* Main Score Display & Multi-Factor Decomposition Grid */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-5 items-center">
        {/* Big Score Readout */}
        <div className="md:col-span-4 flex items-center space-x-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800/80">
          <div
            className={`w-24 h-24 rounded-2xl border-2 flex flex-col items-center justify-center shadow-lg transition-all ${getCRSColor(
              crs,
              isVeto
            )}`}
          >
            <span className="text-3xl font-black font-mono tracking-tight">
              {crs !== null ? crs.toFixed(1) : '0.0'}
            </span>
            <span className="text-[10px] uppercase font-bold tracking-wider opacity-80 mt-0.5">
              / 100 CRS
            </span>
          </div>

          <div className="space-y-1.5 flex-1 min-w-0">
            <div className="text-xs font-mono text-slate-400 flex items-center justify-between">
              <span>Safety State:</span>
              <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold border ${getTargetBadgeStyle(recState)}`}>
                {recState || 'IDLE'}
              </span>
            </div>
            <div className="text-xs font-mono text-slate-400 flex items-center justify-between">
              <span>Voice Intent:</span>
              <span className="text-cyan-300 font-bold truncate max-w-[120px]">
                {latestFusion?.voice_command || 'IDLE'}
              </span>
            </div>
            <div className="text-xs font-mono text-slate-400 flex items-center justify-between">
              <span>Stick Vector:</span>
              <span className="text-blue-300 font-bold truncate max-w-[120px]">
                {latestFusion?.joystick_direction || 'CENTER'}
              </span>
            </div>
          </div>
        </div>

        {/* 3 Multimodal Factor Decompositions */}
        <div className="md:col-span-8 grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Factor 1: Semantic S */}
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/70 space-y-1">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="text-slate-400">Semantic (S)</span>
              <span className="text-sky-400 font-bold">
                {latestFusion ? `${(latestFusion.semantic_reliability * 100).toFixed(0)}%` : '0%'}
              </span>
            </div>
            <div className="w-full bg-slate-800/80 h-2 rounded-full overflow-hidden">
              <div
                className="bg-sky-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${latestFusion ? Math.min(100, latestFusion.semantic_reliability * 100) : 0}%` }}
              />
            </div>
            <div className="text-[10px] text-slate-500 font-mono">Weight: 35% • Whisper STT</div>
          </div>

          {/* Factor 2: Motor Agreement M */}
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/70 space-y-1">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="text-slate-400">Motor Agree (M)</span>
              <span className="text-indigo-400 font-bold">
                {latestFusion ? `${(latestFusion.motor_agreement * 100).toFixed(0)}%` : '0%'}
              </span>
            </div>
            <div className="w-full bg-slate-800/80 h-2 rounded-full overflow-hidden">
              <div
                className="bg-indigo-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${latestFusion ? Math.min(100, latestFusion.motor_agreement * 100) : 0}%` }}
              />
            </div>
            <div className="text-[10px] text-slate-500 font-mono">Weight: 50% • Cosine Vector</div>
          </div>

          {/* Factor 3: Context Consistency C */}
          <div className="bg-slate-950/60 p-3 rounded-xl border border-slate-800/70 space-y-1">
            <div className="flex justify-between items-center text-xs font-mono">
              <span className="text-slate-400">Context (C)</span>
              <span className="text-emerald-400 font-bold">
                {latestFusion ? `${(latestFusion.context_consistency * 100).toFixed(0)}%` : '0%'}
              </span>
            </div>
            <div className="w-full bg-slate-800/80 h-2 rounded-full overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all duration-300"
                style={{ width: `${latestFusion ? Math.min(100, latestFusion.context_consistency * 100) : 0}%` }}
              />
            </div>
            <div className="text-[10px] text-slate-500 font-mono">Weight: 15% • Δt Offset</div>
          </div>
        </div>
      </div>

      {/* Contradiction Alert Banner (if contradiction veto asserted) */}
      {isVeto && (
        <div className="bg-rose-950/80 border border-rose-600 rounded-xl p-3 flex items-center space-x-3 animate-pulse">
          <ShieldAlert className="w-5 h-5 text-rose-400 shrink-0" />
          <div className="text-xs text-rose-200 font-mono flex-1">
            <span className="font-bold text-rose-300 uppercase">ZERO-OVERRIDE CONTRADICTION VETO ASSERTED: </span>
            {latestFusion?.contradiction_reason || 'Verbal command opposes joystick directional deflection.'}
            <span className="block text-[11px] text-rose-400 mt-0.5">
              CRS clamped to max 30.0 • Safety Gateway locks out physical / simulated movement.
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
