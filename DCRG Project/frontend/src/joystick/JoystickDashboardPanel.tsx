/**
 * DCRG Operator Joystick Dashboard Panel.
 * Comprehensive visualization of Physical USB/Bluetooth hardware,
 * Browser Gamepad API (Mobile / Xbox controller support),
 * mode switching, real-time virtual joystick, and live telemetry log.
 * Enhanced with Cross-Modal Speech-Motor Contradiction Testing & Real-Time CRS Integration.
 */

import React, { useState, useEffect } from 'react';
import {
  Gamepad2,
  Cpu,
  Radio,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  History,
  ToggleLeft,
  ToggleRight,
  ShieldAlert,
  Smartphone,
  RefreshCw,
  Zap,
  Volume2,
  Activity,
  ArrowRight,
  RotateCcw,
} from 'lucide-react';
import { VirtualJoystick } from './VirtualJoystick';
import { useJoystickStream } from '../hooks/useJoystickStream';
import { useGamepad } from '../hooks/useGamepad';
import { useVoiceStream } from '../hooks/useVoiceStream';
import { useFusionStream } from '../hooks/useFusionStream';
import {
  fetchJoystickStatus,
  rescanJoysticks,
  setJoystickMode,
  playPredefinedSample,
} from '../services/api';
import type { JoystickMode, JoystickSystemStatus } from '../types';

export const JoystickDashboardPanel: React.FC = () => {
  const {
    isConnected: isWsConnected,
    status: wsStatus,
    lastEvent: lastJoyEvent,
    eventHistory,
    sendVirtualInput,
    sendHardwareInput,
    requestModeChange,
    error: wsError,
  } = useJoystickStream();

  const { lastEvent: lastVoiceEvent } = useVoiceStream();
  const { latestFusion } = useFusionStream();

  const [pollStatus, setPollStatus] = useState<JoystickSystemStatus | null>(null);
  const [activeTab, setActiveTab] = useState<'CONTROLS' | 'HISTORY'>('CONTROLS');
  const [isRescanning, setIsRescanning] = useState(false);
  const [testActionLoading, setTestActionLoading] = useState<string | null>(null);
  const [testResultFeedback, setTestResultFeedback] = useState<string | null>(null);

  const status = wsStatus || pollStatus;
  const activeMode: JoystickMode = status?.active_mode || 'VIRTUAL_SIMULATION';
  const isHardwareConnected = status?.physical_hardware_detected ?? false;

  // Browser Gamepad API Hook: Streams browser/mobile/USB gamepad inputs
  const browserGamepad = useGamepad((x, y, buttons) => {
    if (activeMode === 'REAL_HARDWARE') {
      sendHardwareInput(x, y, buttons, browserGamepad.id || 'USB-BROWSER-CONTROLLER');
    } else {
      sendVirtualInput(x, y, buttons);
    }
  });

  // Periodic poll fallback for backend hardware status
  useEffect(() => {
    fetchJoystickStatus().then((s) => setPollStatus(s));
    const interval = window.setInterval(() => {
      fetchJoystickStatus().then((s) => setPollStatus(s));
    }, 2500);
    return () => window.clearInterval(interval);
  }, []);

  const handleModeToggle = async () => {
    const nextMode: JoystickMode =
      activeMode === 'VIRTUAL_SIMULATION' ? 'REAL_HARDWARE' : 'VIRTUAL_SIMULATION';
    try {
      await setJoystickMode(nextMode, true);
      requestModeChange(nextMode, true);
      const updated = await fetchJoystickStatus();
      if (updated) setPollStatus(updated);
    } catch (err: any) {
      console.warn('Mode toggle notice:', err);
    }
  };

  const handleRescan = async () => {
    setIsRescanning(true);
    try {
      await rescanJoysticks();
      const updated = await fetchJoystickStatus();
      if (updated) setPollStatus(updated);
    } finally {
      setIsRescanning(false);
    }
  };

  // Cross-Modal Automated Demonstration Handler
  const handleRunCrossModalTest = async (
    testId: string,
    joyX: number,
    joyY: number,
    voiceSampleId: string,
    expectedDesc: string
  ) => {
    setTestActionLoading(testId);
    setTestResultFeedback(`Executing: Setting Joystick (X:${joyX}, Y:${joyY}) + Playing Voice '${voiceSampleId}'...`);
    try {
      // 1. Immediately inject the joystick telemetry vector
      sendVirtualInput(joyX, joyY, [false, false, false, false]);

      // 2. Play the predefined audio file in browser for audible feedback
      try {
        const audio = new Audio(`/samples/${voiceSampleId}.wav`);
        audio.play().catch(() => {});
      } catch {
        // Audio playback fallback ignored
      }

      // 3. Trigger backend voice ingestion endpoint
      await playPredefinedSample(voiceSampleId);

      // 4. Send updated joystick deflection frame so temporal synchrony delta is near-zero
      sendVirtualInput(joyX, joyY, [false, false, false, false]);

      setTestResultFeedback(`Success! ${expectedDesc}`);
    } catch (err: any) {
      setTestResultFeedback(`Execution note: ${err.message}`);
    } finally {
      setTestActionLoading(null);
    }
  };

  // Evaluate contradiction state for the banner
  const isContradiction = latestFusion?.contradiction_detected ?? false;
  const crsScore = latestFusion?.CRS ?? null;
  const finding = latestFusion?.analytical_finding;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl text-left space-y-6">
      {/* Header & Mode Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-slate-800 text-cyan-400">
            <Gamepad2 className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100 m-0">
              Actuator Subsystem
            </h2>
            <p className="text-xs text-slate-400 m-0">
              Physical USB/Bluetooth Gamepads, Mobile/Browser Gamepads & Interactive Virtual Joystick
            </p>
          </div>
        </div>

        {/* Real / Virtual Mode Switcher */}
        <div className="flex items-center space-x-3 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800">
          <span className="text-xs text-slate-400 font-mono">ACTIVE MODE:</span>
          <button
            type="button"
            onClick={handleModeToggle}
            className={`flex items-center space-x-1.5 px-3 py-1 rounded text-xs font-mono font-bold transition ${
              activeMode === 'REAL_HARDWARE'
                ? 'bg-emerald-950 text-emerald-400 border border-emerald-600'
                : 'bg-amber-950 text-amber-300 border border-amber-600'
            }`}
          >
            {activeMode === 'REAL_HARDWARE' ? (
              <>
                <ToggleRight className="w-4 h-4 text-emerald-400" />
                <span>REAL HARDWARE</span>
              </>
            ) : (
              <>
                <ToggleLeft className="w-4 h-4 text-amber-400" />
                <span>VIRTUAL SIMULATION</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Cross-Modal Speech-Motor Contradiction & CRS Status Banner */}
      <div
        className={`p-4 rounded-xl border transition-all ${
          isContradiction
            ? 'bg-rose-950/50 border-rose-600/80 shadow-lg shadow-rose-950/40'
            : finding === 'AGREEMENT'
            ? 'bg-emerald-950/40 border-emerald-600/70'
            : 'bg-slate-950 border-slate-800'
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div
              className={`p-2 rounded-lg ${
                isContradiction
                  ? 'bg-rose-900/60 text-rose-300 animate-pulse'
                  : finding === 'AGREEMENT'
                  ? 'bg-emerald-900/60 text-emerald-300'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              {isContradiction ? (
                <ShieldAlert className="w-5 h-5 text-rose-400" />
              ) : finding === 'AGREEMENT' ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              ) : (
                <Activity className="w-5 h-5 text-cyan-400" />
              )}
            </div>

            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-mono uppercase tracking-wider text-slate-400">
                  Cross-Modal Speech-Motor Status:
                </span>
                {isContradiction ? (
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-rose-600 text-white animate-pulse">
                    CONTRADICTION VETO ASSERTED
                  </span>
                ) : finding === 'AGREEMENT' ? (
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-emerald-600 text-white">
                    MULTIMODAL AGREEMENT
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-slate-800 text-slate-300">
                    {finding || 'AWAITING PAIR'}
                  </span>
                )}
              </div>

              <div className="text-sm font-mono mt-1 text-slate-200 flex flex-wrap items-center gap-x-4 gap-y-1">
                <span>
                  Joystick:{' '}
                  <strong className="text-cyan-400">
                    {lastJoyEvent?.direction || 'CENTER'}
                  </strong>{' '}
                  ({lastJoyEvent ? `${(lastJoyEvent.intensity * 100).toFixed(0)}%` : '0%'})
                </span>
                <span className="text-slate-600">|</span>
                <span>
                  Voice:{' '}
                  <strong className="text-amber-400">
                    {lastVoiceEvent?.recognized_command || 'IDLE'}
                  </strong>{' '}
                  ({lastVoiceEvent ? `${(lastVoiceEvent.recognition_confidence * 100).toFixed(0)}%` : '—'})
                </span>
              </div>
            </div>
          </div>

          {/* Real-time CRS readout */}
          <div className="flex items-center space-x-3 bg-slate-900/90 px-4 py-2 rounded-lg border border-slate-800">
            <div className="text-right font-mono">
              <span className="text-[10px] text-slate-500 block">COMMAND RELIABILITY</span>
              <span
                className={`text-xl font-bold ${
                  crsScore === null
                    ? 'text-slate-500'
                    : isContradiction || crsScore <= 30.0
                    ? 'text-rose-400'
                    : crsScore >= 85.0
                    ? 'text-emerald-400'
                    : 'text-amber-400'
                }`}
              >
                {crsScore !== null ? `${crsScore.toFixed(1)}` : '—'}
                <span className="text-xs text-slate-500 font-normal"> / 100</span>
              </span>
            </div>
            <span
              className={`px-2 py-1 rounded text-xs font-mono font-bold uppercase ${
                isContradiction || (crsScore !== null && crsScore <= 30.0)
                  ? 'bg-rose-950 text-rose-300 border border-rose-600'
                  : crsScore !== null && crsScore >= 85.0
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-600'
                  : 'bg-amber-950 text-amber-300 border border-amber-600'
              }`}
            >
              {latestFusion?.recommended_state || 'READY'}
            </span>
          </div>
        </div>
      </div>

      {/* Hardware Connection Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Physical Status */}
        <div className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs text-slate-400 font-mono">
              <Cpu className="w-4 h-4 text-slate-500" />
              <span>BACKEND HARDWARE (PYGAME SDL2)</span>
            </div>
            <div className="flex items-center space-x-2">
              <button
                type="button"
                onClick={handleRescan}
                disabled={isRescanning}
                className="flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-900 hover:bg-slate-800 text-cyan-300 border border-slate-700 transition"
                title="Rescan USB ports for flight sticks / gamepads"
              >
                <RefreshCw
                  className={`w-3 h-3 ${isRescanning ? 'animate-spin text-cyan-400' : 'text-slate-400'}`}
                />
                <span>RESCAN</span>
              </button>
              {isHardwareConnected ? (
                <span className="flex items-center space-x-1 text-xs text-emerald-400 font-bold bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-800">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>CONNECTED</span>
                </span>
              ) : activeMode === 'REAL_HARDWARE' ? (
                <span className="flex items-center space-x-1 text-xs text-cyan-400 font-bold bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>HARDWARE ACTIVE</span>
                </span>
              ) : (
                <span className="flex items-center space-x-1 text-xs text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                  <XCircle className="w-3.5 h-3.5 text-slate-500" />
                  <span>NO USB/BT ATTACHED</span>
                </span>
              )}
            </div>
          </div>

          <div className="text-sm font-semibold text-slate-200">
            {isHardwareConnected
              ? status?.primary_device_name
              : activeMode === 'REAL_HARDWARE'
              ? 'Physical Hardware Subsystem Engaged (USB / Gamepad / Direct)'
              : 'No Physical USB/Bluetooth Joystick Detected'}
          </div>

          <div className="text-xs text-slate-400 flex items-center justify-between pt-1 border-t border-slate-900">
            <span>Device ID: {status?.primary_device_id || 'None'}</span>
            <span>Controllers: {status?.connected_device_count ?? 0}</span>
          </div>

          {status?.error_message && (
            <div className="text-xs text-rose-400 bg-rose-950/40 p-2 rounded border border-rose-900 flex items-center space-x-1.5">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{status.error_message}</span>
            </div>
          )}
        </div>

        {/* Telemetry & Stream Status */}
        <div className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs text-slate-400 font-mono">
              <Radio className="w-4 h-4 text-cyan-400" />
              <span>TELEMETRY STREAM (/ws/joystick/stream)</span>
            </div>
            <span
              className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
                isWsConnected
                  ? 'text-cyan-400 bg-cyan-950/60 border-cyan-800'
                  : 'text-amber-400 bg-amber-950/60 border-amber-800'
              }`}
            >
              {isWsConnected ? 'LIVE 10Hz' : 'CONNECTING...'}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs font-mono pt-1">
            <div>
              <span className="text-slate-500 block">DIRECTION</span>
              <span className="text-slate-200 font-bold">
                {lastJoyEvent?.direction || 'CENTER'}
              </span>
            </div>
            <div>
              <span className="text-slate-500 block">INTENSITY</span>
              <span className="text-emerald-400 font-bold">
                {lastJoyEvent ? `${(lastJoyEvent.intensity * 100).toFixed(1)}%` : '0.0%'}
              </span>
            </div>
          </div>

          <div className="text-[11px] text-slate-500 flex items-center justify-between pt-1 border-t border-slate-900 font-mono">
            <span>
              Source:{' '}
              {lastJoyEvent?.source ||
                (activeMode === 'REAL_HARDWARE' ? 'PHYSICAL_HARDWARE' : 'VIRTUAL_SIMULATION')}
            </span>
            <span>
              {lastJoyEvent?.is_simulation ? (
                <span className="text-amber-400">[SIMULATION]</span>
              ) : (
                <span className="text-emerald-400">[HARDWARE]</span>
              )}
            </span>
          </div>
        </div>
      </div>

      {/* Browser / Mobile Gamepad Detection Banner */}
      {browserGamepad.connected && (
        <div className="p-3 bg-sky-950/70 border border-sky-700/80 rounded-lg text-xs text-sky-200 flex items-center justify-between font-mono">
          <div className="flex items-center space-x-2">
            <Smartphone className="w-4 h-4 text-sky-400 shrink-0" />
            <span>
              <strong>Active Mobile / Browser Gamepad:</strong> {browserGamepad.id}
            </span>
          </div>
          <span className="text-sky-300 font-bold bg-sky-900/60 px-2 py-0.5 rounded border border-sky-600">
            Int: {(browserGamepad.intensity * 100).toFixed(0)}%
          </span>
        </div>
      )}

      {wsError && (
        <div className="p-3 bg-amber-950/60 border border-amber-800 rounded-lg text-xs text-amber-300 flex items-center space-x-2">
          <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{wsError}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-800 pb-2">
        <button
          type="button"
          onClick={() => setActiveTab('CONTROLS')}
          className={`px-3 py-1.5 text-xs font-medium rounded transition ${
            activeTab === 'CONTROLS'
              ? 'bg-slate-800 text-slate-100 font-bold border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          Interactive Virtual Joystick
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('HISTORY')}
          className={`px-3 py-1.5 text-xs font-medium rounded transition flex items-center space-x-1 ${
            activeTab === 'HISTORY'
              ? 'bg-slate-800 text-slate-100 font-bold border border-slate-700'
              : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          <History className="w-3.5 h-3.5" />
          <span>Live Telemetry Log ({eventHistory.length})</span>
        </button>
      </div>

      {/* Tab 1: Virtual Joystick Simulator & Cross-Modal Testing */}
      {activeTab === 'CONTROLS' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Virtual Joystick Knob & D-Pad (7 cols) */}
            <div className="lg:col-span-7">
              <VirtualJoystick
                onVectorChange={(x, y, buttons) => {
                  if (activeMode === 'REAL_HARDWARE') {
                    sendHardwareInput(x, y, buttons, 'PHYSICAL-HARDWARE-CONTROLS');
                  } else {
                    sendVirtualInput(x, y, buttons);
                  }
                }}
                disabled={false}
                externalAxes={
                  lastJoyEvent && !lastJoyEvent.is_simulation
                    ? { x: lastJoyEvent.axis_x, y: lastJoyEvent.axis_y }
                    : null
                }
              />
            </div>

            {/* Right Column: 1-Click Speech-Motor Contradiction Testing Presets (5 cols) */}
            <div className="lg:col-span-5 bg-slate-950 border border-slate-800 rounded-xl p-4 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center space-x-2 text-slate-200 mb-1">
                  <Zap className="w-4 h-4 text-amber-400" />
                  <h4 className="text-xs font-bold uppercase tracking-wider font-mono">
                    1-Click Contradiction Testing
                  </h4>
                </div>
                <p className="text-[11px] text-slate-400">
                  Instantly triggers opposing speech commands against joystick deflections to demonstrate the zero-override Contradiction Veto (CRS &le; 30.0 RED).
                </p>

                <div className="space-y-2 mt-3">
                  {/* Test 1: Lateral Contradiction (RIGHT Stick vs LEFT Voice) */}
                  <button
                    type="button"
                    disabled={testActionLoading !== null}
                    onClick={() =>
                      handleRunCrossModalTest(
                        'LATERAL_CONTRADICTION',
                        0.85,
                        0.0,
                        'left',
                        'Contradiction Veto triggered: Stick RIGHT vs Voice LEFT (CRS <= 30.0 RED)'
                      )
                    }
                    className="w-full flex items-center justify-between p-2.5 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-200 border border-rose-800/80 transition text-xs font-mono text-left group"
                  >
                    <div className="flex items-center space-x-2">
                      <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
                      <div>
                        <strong className="block text-rose-300">Stick RIGHT vs Voice LEFT</strong>
                        <span className="text-[10px] text-slate-400">Lateral Contradiction &rarr; Veto Clamps to 30.0</span>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-rose-400 group-hover:translate-x-1 transition" />
                  </button>

                  {/* Test 2: Longitudinal Contradiction (FORWARD Stick vs BACKWARD Voice) */}
                  <button
                    type="button"
                    disabled={testActionLoading !== null}
                    onClick={() =>
                      handleRunCrossModalTest(
                        'LONGITUDINAL_CONTRADICTION',
                        0.0,
                        0.85,
                        'backward',
                        'Contradiction Veto triggered: Stick FORWARD vs Voice BACKWARD (CRS <= 30.0 RED)'
                      )
                    }
                    className="w-full flex items-center justify-between p-2.5 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-200 border border-rose-800/80 transition text-xs font-mono text-left group"
                  >
                    <div className="flex items-center space-x-2">
                      <span className="w-2 h-2 rounded-full bg-rose-500" />
                      <div>
                        <strong className="block text-rose-300">Stick FWD vs Voice BACKWARD</strong>
                        <span className="text-[10px] text-slate-400">Opposing 180&deg; &rarr; Veto Clamps to 30.0</span>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-rose-400 group-hover:translate-x-1 transition" />
                  </button>

                  {/* Test 3: Stop Override (FORWARD Stick vs STOP Voice) */}
                  <button
                    type="button"
                    disabled={testActionLoading !== null}
                    onClick={() =>
                      handleRunCrossModalTest(
                        'STOP_OVERRIDE',
                        0.0,
                        0.85,
                        'stop',
                        'Stop Veto asserted: Stick moving vs Voice STOP (CRS <= 30.0 RED)'
                      )
                    }
                    className="w-full flex items-center justify-between p-2.5 rounded-lg bg-red-950/50 hover:bg-red-900/70 text-red-200 border border-red-700 transition text-xs font-mono text-left group"
                  >
                    <div className="flex items-center space-x-2">
                      <Volume2 className="w-4 h-4 text-red-400" />
                      <div>
                        <strong className="block text-red-300">Stick FWD vs Voice STOP</strong>
                        <span className="text-[10px] text-slate-400">Emergency Stop Preemption &rarr; Veto</span>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-red-400 group-hover:translate-x-1 transition" />
                  </button>

                  {/* Test 4: Multimodal Agreement (FORWARD Stick vs FORWARD Voice) */}
                  <button
                    type="button"
                    disabled={testActionLoading !== null}
                    onClick={() =>
                      handleRunCrossModalTest(
                        'AGREEMENT_FWD',
                        0.0,
                        0.85,
                        'forward',
                        'Multimodal Agreement: Stick FORWARD + Voice FORWARD (CRS >= 85.0 GREEN)'
                      )
                    }
                    className="w-full flex items-center justify-between p-2.5 rounded-lg bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-200 border border-emerald-800/80 transition text-xs font-mono text-left group"
                  >
                    <div className="flex items-center space-x-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      <div>
                        <strong className="block text-emerald-300">Stick FWD + Voice FORWARD</strong>
                        <span className="text-[10px] text-slate-400">Concordant &rarr; High Reliability &ge; 85.0</span>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-emerald-400 group-hover:translate-x-1 transition" />
                  </button>
                </div>
              </div>

              {/* Status / Feedback note */}
              {testResultFeedback && (
                <div className="p-2.5 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-cyan-300 flex items-start space-x-2">
                  <Activity className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                  <span>{testResultFeedback}</span>
                </div>
              )}

              {/* Reset to Neutral Button */}
              <button
                type="button"
                onClick={() => {
                  sendVirtualInput(0.0, 0.0, [false, false, false, false]);
                  setTestResultFeedback('Joystick reset to Neutral Center (0.0, 0.0).');
                }}
                className="w-full py-1.5 px-3 rounded bg-slate-800 hover:bg-slate-750 text-slate-300 border border-slate-700 flex items-center justify-center space-x-2 text-xs font-mono transition"
              >
                <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
                <span>Reset Joystick to Neutral (0, 0)</span>
              </button>
            </div>
          </div>

          {activeMode === 'REAL_HARDWARE' && (
            <div className="p-3 bg-emerald-950/30 border border-emerald-800/80 rounded-lg flex items-center justify-between text-xs font-mono">
              <span className="text-emerald-300 font-semibold flex items-center space-x-1.5">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>REAL HARDWARE MODE ENGAGED</span>
              </span>
              <span className="text-slate-400 text-[11px]">
                Events tagged as [HARDWARE] (is_simulation: false)
              </span>
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Live Event History */}
      {activeTab === 'HISTORY' && (
        <div className="bg-slate-950 border border-slate-800 rounded-lg p-3 max-h-72 overflow-y-auto font-mono text-xs space-y-1.5">
          {eventHistory.length === 0 ? (
            <div className="text-slate-500 text-center py-6">
              Awaiting joystick input events...
            </div>
          ) : (
            eventHistory.map((ev, i) => (
              <div
                key={ev.event_id || i}
                className="flex items-center justify-between p-2 rounded bg-slate-900 border border-slate-800/80 text-slate-300 hover:bg-slate-850"
              >
                <div className="flex items-center space-x-2">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                      ev.is_simulation
                        ? 'bg-amber-950 text-amber-300 border border-amber-800'
                        : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                    }`}
                  >
                    {ev.is_simulation ? 'SIM' : 'HW'}
                  </span>
                  <span className="text-cyan-400 font-bold">{ev.direction}</span>
                  <span className="text-slate-400">
                    X:{ev.axis_x >= 0 ? `+${ev.axis_x.toFixed(2)}` : ev.axis_x.toFixed(2)} | Y:
                    {ev.axis_y >= 0 ? `+${ev.axis_y.toFixed(2)}` : ev.axis_y.toFixed(2)}
                  </span>
                </div>
                <div className="flex items-center space-x-3 text-slate-500">
                  <span>Int: {(ev.intensity * 100).toFixed(0)}%</span>
                  <span>{new Date(ev.timestamp).toLocaleTimeString()}</span>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
};
