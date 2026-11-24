import React, { useState } from 'react';
import {
  GitMerge,
  Clock,
  Mic,
  Gamepad2,
  AlertCircle,
  Sliders,
  CheckCircle2,
} from 'lucide-react';
import { useSyncStream } from '../hooks/useSyncStream';
import { useFusionStream } from '../hooks/useFusionStream';
import type { SynchronizationStatus } from '../types';

export const SynchronizationDashboardPanel: React.FC = () => {
  const {
    syncStatus,
    latestCorrelation,
    correlationHistory,
    isWsConnected,
    updateSyncWindow,
  } = useSyncStream();
  const { latestFusion } = useFusionStream();

  const [sliderWindow, setSliderWindow] = useState<number>(syncStatus?.sync_window_ms || 150);

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = parseFloat(e.target.value);
    setSliderWindow(val);
  };

  const handleSliderCommit = async () => {
    await updateSyncWindow(sliderWindow);
  };

  const renderStatusBadge = (status?: SynchronizationStatus) => {
    switch (status) {
      case 'SYNCHRONIZED':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-950/90 text-emerald-300 border border-emerald-700 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>SYNCHRONIZED</span>
          </span>
        );
      case 'VOICE_ONLY':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-sky-950/90 text-sky-300 border border-sky-700">
            <span className="w-2 h-2 rounded-full bg-sky-400" />
            <span>VOICE_ONLY</span>
          </span>
        );
      case 'JOYSTICK_ONLY':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-indigo-950/90 text-indigo-300 border border-indigo-700">
            <span className="w-2 h-2 rounded-full bg-indigo-400" />
            <span>JOYSTICK_ONLY</span>
          </span>
        );
      case 'OUT_OF_WINDOW':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-amber-950/90 text-amber-300 border border-amber-700">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>OUT_OF_WINDOW</span>
          </span>
        );
      case 'DELAYED':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-orange-950/90 text-orange-300 border border-orange-700">
            <span className="w-2 h-2 rounded-full bg-orange-400" />
            <span>DELAYED</span>
          </span>
        );
      case 'STALE':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-rose-950/90 text-rose-300 border border-rose-700">
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            <span>STALE</span>
          </span>
        );
      case 'INVALID_TIMESTAMP':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-red-950/90 text-red-300 border border-red-700">
            <AlertCircle className="w-3.5 h-3.5 text-red-400" />
            <span>INVALID_TIMESTAMP</span>
          </span>
        );
      case 'DUPLICATE':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-purple-950/90 text-purple-300 border border-purple-700">
            <span className="w-2 h-2 rounded-full bg-purple-400" />
            <span>DUPLICATE</span>
          </span>
        );
      default:
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono text-slate-400 bg-slate-800 border border-slate-700">
            <span>AWAITING INPUT</span>
          </span>
        );
    }
  };

  const deltaMs = latestCorrelation?.timestamp_difference_ms ?? null;
  const currentWindow = syncStatus?.sync_window_ms ?? 150;

  return (
    <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl text-left space-y-6">
      {/* Panel Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-xl bg-violet-950/50 border border-violet-800/60">
            <GitMerge className="w-6 h-6 text-violet-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-slate-100">
              Event Synchronization & Correlation Engine
            </h2>
            <p className="text-xs text-slate-400">
              Phase 4 • Asynchronous Modality Alignment (Voice STT ↔ 50Hz Joystick)
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3 self-start md:self-auto">
          {renderStatusBadge(latestCorrelation?.synchronization_status)}
          <span
            className={`text-xs px-2.5 py-1 rounded-full font-mono border ${
              isWsConnected
                ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
                : 'bg-rose-950/40 text-rose-400 border-rose-800/60'
            }`}
          >
            WS: {isWsConnected ? 'SYNC STREAM ACTIVE' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      {/* Control Bar: Synchronization Window Adjustment */}
      <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3 w-full md:w-auto">
          <Sliders className="w-5 h-5 text-violet-400 shrink-0" />
          <div>
            <div className="text-xs font-mono text-slate-300 font-semibold">
              SYNCHRONIZATION WINDOW (τ_sync): <span className="text-violet-400 font-bold">{sliderWindow.toFixed(0)} ms</span>
            </div>
            <div className="text-[11px] text-slate-500">
              Experimental prototype setting • Default 150 ms (DCRG-ARCH-004)
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-4 w-full md:w-80">
          <span className="text-[11px] font-mono text-slate-500">50ms</span>
          <input
            type="range"
            min="50"
            max="400"
            step="10"
            value={sliderWindow}
            onChange={handleSliderChange}
            onMouseUp={handleSliderCommit}
            onTouchEnd={handleSliderCommit}
            className="w-full accent-violet-500 cursor-pointer"
          />
          <span className="text-[11px] font-mono text-slate-500">400ms</span>
        </div>
      </div>

      {/* Correlation Primary Matrix: Voice vs Joystick Pairing */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-stretch">
        {/* Left Column: Voice Modality Inception */}
        <div className="p-4 bg-slate-950/40 border border-slate-800/80 rounded-xl space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2 text-cyan-400">
                <Mic className="w-4 h-4" />
                <span className="text-xs font-mono font-bold uppercase tracking-wider">Voice Modality</span>
              </div>
              <span
                className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                  latestCorrelation?.voice_available
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                    : 'bg-slate-800 text-slate-500'
                }`}
              >
                {latestCorrelation?.voice_available ? 'AVAILABLE' : 'ABSENT'}
              </span>
            </div>

            <div className="mt-3 space-y-2">
              <div className="text-xs font-mono text-slate-400">Command Primitive:</div>
              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg text-lg font-mono font-bold text-cyan-300">
                {latestCorrelation?.voice_command || '— (No Speech)'}
              </div>

              <div className="text-xs font-mono text-slate-400">Transcript:</div>
              <div className="p-2 bg-slate-900/60 border border-slate-800/60 rounded text-xs text-slate-300 italic min-h-[36px]">
                {latestCorrelation?.voice_event?.transcript ? `"${latestCorrelation.voice_event.transcript}"` : '—'}
              </div>

              <div className="text-[11px] font-mono text-slate-500 space-y-0.5 pt-1">
                <div>ID: {latestCorrelation?.voice_event_id ? latestCorrelation.voice_event_id.slice(0, 13) + '...' : '—'}</div>
                <div>Event Time: {latestCorrelation?.voice_event?.timestamp ? new Date(latestCorrelation.voice_event.timestamp).toLocaleTimeString() : '—'}</div>
              </div>
            </div>
          </div>
        </div>

        {/* Center Column: Temporal Alignment Core */}
        <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-4 flex flex-col justify-between text-center">
          <div>
            <div className="text-xs font-mono text-slate-400 uppercase tracking-wider border-b border-slate-800 pb-2">
              Temporal Divergence (Δt)
            </div>

            <div className="my-4">
              <div className="text-3xl font-black font-mono text-violet-400">
                {deltaMs !== null ? `${deltaMs.toFixed(1)}` : '—'} <span className="text-sm font-normal text-slate-500">ms</span>
              </div>
              <div className="text-xs font-mono text-slate-400 mt-1">
                Allowed Window: ≤ {currentWindow} ms
              </div>
            </div>

            {/* Visual Delta Meter */}
            <div className="space-y-1 text-left">
              <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-200 ${
                    deltaMs === null
                      ? 'bg-slate-700 w-0'
                      : deltaMs <= currentWindow
                      ? 'bg-emerald-400'
                      : 'bg-rose-500'
                  }`}
                  style={{ width: `${deltaMs === null ? 0 : Math.min(100, (deltaMs / currentWindow) * 100)}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] font-mono text-slate-500">
                <span>0 ms</span>
                <span>{currentWindow / 2} ms</span>
                <span>{currentWindow} ms</span>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg flex items-center justify-between text-xs font-mono">
              <span className="text-slate-400">Resulting CRS:</span>
              <span
                className={`font-bold px-2 py-0.5 rounded border ${
                  latestFusion && latestFusion.CRS >= 85
                    ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                    : latestFusion && latestFusion.CRS >= 50
                    ? 'bg-amber-950 text-amber-300 border-amber-700'
                    : 'bg-rose-950 text-rose-300 border-rose-700'
                }`}
              >
                {latestFusion ? `${latestFusion.CRS.toFixed(1)} / 100 (${latestFusion.recommended_state || 'IDLE'})` : 'AWAITING'}
              </span>
            </div>

            <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg text-xs font-mono text-slate-300 text-left">
              <span className="text-slate-500">Correlation Reason:</span>
              <div className="mt-0.5 font-semibold text-slate-200">
                {latestCorrelation?.correlation_reason || 'Awaiting multi-modal events...'}
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Joystick Modality Inception */}
        <div className="p-4 bg-slate-950/40 border border-slate-800/80 rounded-xl space-y-3 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2 text-emerald-400">
                <Gamepad2 className="w-4 h-4" />
                <span className="text-xs font-mono font-bold uppercase tracking-wider">Joystick Modality</span>
              </div>
              <span
                className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                  latestCorrelation?.joystick_available
                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                    : 'bg-slate-800 text-slate-500'
                }`}
              >
                {latestCorrelation?.joystick_available ? 'AVAILABLE' : 'ABSENT'}
              </span>
            </div>

            <div className="mt-3 space-y-2">
              <div className="text-xs font-mono text-slate-400">Deflection Direction:</div>
              <div className="p-2.5 bg-slate-900 border border-slate-800 rounded-lg text-lg font-mono font-bold text-emerald-300">
                {latestCorrelation?.joystick_direction || '— (Neutral)'}
              </div>

              <div className="text-xs font-mono text-slate-400">Intensity / Magnitude:</div>
              <div className="p-2 bg-slate-900/60 border border-slate-800/60 rounded text-xs font-mono text-slate-300 flex justify-between items-center min-h-[36px]">
                <span>Intensity:</span>
                <span className="text-emerald-400 font-bold">
                  {latestCorrelation?.joystick_intensity !== null && latestCorrelation?.joystick_intensity !== undefined
                    ? `${(latestCorrelation.joystick_intensity * 100).toFixed(0)}%`
                    : '0%'}
                </span>
              </div>

              <div className="text-[11px] font-mono text-slate-500 space-y-0.5 pt-1">
                <div>ID: {latestCorrelation?.joystick_event_id ? latestCorrelation.joystick_event_id.slice(0, 13) + '...' : '—'}</div>
                <div>Event Time: {latestCorrelation?.joystick_event?.timestamp ? new Date(latestCorrelation.joystick_event.timestamp).toLocaleTimeString() : '—'}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Telemetry Counter Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl">
          <div className="text-[11px] font-mono text-slate-400">SYNCHRONIZED PAIRS</div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-1">
            {syncStatus?.total_synchronized_count ?? 0}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Matched within τ_sync</div>
        </div>

        <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl">
          <div className="text-[11px] font-mono text-slate-400">OUT OF WINDOW</div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-1">
            {syncStatus?.total_out_of_window_count ?? 0}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Divergence &gt; τ_sync</div>
        </div>

        <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl">
          <div className="text-[11px] font-mono text-slate-400">DELAYED EVENTS</div>
          <div className="text-2xl font-bold font-mono text-orange-400 mt-1">
            {syncStatus?.total_delayed_count ?? 0}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Latency &gt; 200 ms</div>
        </div>

        <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl">
          <div className="text-[11px] font-mono text-slate-400">STALE / EXPIRED</div>
          <div className="text-2xl font-bold font-mono text-rose-400 mt-1">
            {syncStatus?.total_stale_count ?? 0}
          </div>
          <div className="text-[10px] text-slate-500 mt-0.5">Exceeded max age (350ms)</div>
        </div>
      </div>

      {/* Visual Timeline of Recent Synchronized Streams */}
      <div className="p-4 bg-slate-950/60 border border-slate-800/80 rounded-xl space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center space-x-2 text-slate-300">
            <Clock className="w-4 h-4 text-violet-400" />
            <span className="text-xs font-mono font-semibold uppercase tracking-wider">
              Asynchronous Event Timeline (Recent 5 Correlations)
            </span>
          </div>
          <span className="text-xs font-mono text-slate-500">
            Buffers: Voice({syncStatus?.voice_buffer_count ?? 0}) • Joy({syncStatus?.joystick_buffer_count ?? 0})
          </span>
        </div>

        {correlationHistory.length === 0 ? (
          <div className="text-xs font-mono text-slate-500 text-center py-4">
            No correlated events recorded yet. Speak a command or move the joystick to observe alignment.
          </div>
        ) : (
          <div className="space-y-2">
            {correlationHistory.slice(0, 5).map((ev) => (
              <div
                key={ev.correlation_id}
                className="p-3 bg-slate-900 border border-slate-800 rounded-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-3 text-xs font-mono"
              >
                <div className="flex items-center space-x-3">
                  <span className="text-slate-500 text-[11px]">
                    {new Date(ev.correlation_timestamp).toLocaleTimeString()}
                  </span>
                  {renderStatusBadge(ev.synchronization_status)}
                </div>

                <div className="flex items-center space-x-4">
                  <div className="flex items-center space-x-1.5">
                    <Mic className="w-3.5 h-3.5 text-cyan-400" />
                    <span className="text-cyan-300 font-bold">{ev.voice_command || 'ABSENT'}</span>
                  </div>
                  <span className="text-slate-600">↔</span>
                  <div className="flex items-center space-x-1.5">
                    <Gamepad2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-300 font-bold">{ev.joystick_direction || 'ABSENT'}</span>
                  </div>
                </div>

                <div className="flex items-center space-x-2 text-slate-400 text-[11px]">
                  <span>Δt:</span>
                  <span className="text-violet-400 font-bold">
                    {ev.timestamp_difference_ms !== null && ev.timestamp_difference_ms !== undefined
                      ? `${ev.timestamp_difference_ms.toFixed(1)} ms`
                      : '—'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Safety Guardrail Notice */}
      <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-start space-x-2.5 text-xs text-slate-400">
        <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
        <p>
          <strong className="text-slate-300">Phase 4 Boundary Notice:</strong> The Synchronization Engine identifies temporal correlation only. It does NOT compute reliability scores (CRS), does NOT authorize movement, and does NOT drive actuators.
        </p>
      </div>
    </div>
  );
};
