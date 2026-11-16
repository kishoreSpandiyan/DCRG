import React, { useState } from 'react';
import {
  Layers,
  ShieldAlert,
  Sliders,
  RotateCcw,
  Zap,
  Gauge,
  Compass,
  Radio,
} from 'lucide-react';
import { useFusionStream } from '../hooks/useFusionStream';
import type {
  CRSStatus,
  AnalyticalFinding,
  MissionMode,
} from '../types';

export const FusionDashboardPanel: React.FC = () => {
  const {
    fusionStatus,
    latestFusion,
    fusionHistory,
    fusionConfig,
    contextState,
    isWsConnected,
    updateContext,
    resetContext,
    manualEvaluate,
  } = useFusionStream();

  // Manual Evaluator Form State
  const [evalVoiceCmd, setEvalVoiceCmd] = useState<string>('FORWARD');
  const [evalVoiceConf, setEvalVoiceConf] = useState<number>(0.92);
  const [evalStress, setEvalStress] = useState<number>(0.10);
  const [evalJoyDir, setEvalJoyDir] = useState<string>('FORWARD');
  const [evalJoyInt, setEvalJoyInt] = useState<number>(0.85);
  const [evalDeltaMs, setEvalDeltaMs] = useState<number>(10.0);
  const [evalLoading, setEvalLoading] = useState<boolean>(false);

  const handleManualRun = async () => {
    setEvalLoading(true);
    await manualEvaluate({
      voice_command: evalVoiceCmd,
      voice_confidence: evalVoiceConf,
      stress_score: evalStress,
      joystick_direction: evalJoyDir,
      joystick_intensity: evalJoyInt,
      sync_delta_ms: evalDeltaMs,
    });
    setEvalLoading(false);
  };

  const handleModeChange = async (mode: MissionMode) => {
    if (contextState) {
      await updateContext({
        ...contextState,
        operating_mode: mode,
      });
    }
  };

  const handleObstacleDistanceChange = async (dist: number) => {
    if (contextState) {
      await updateContext({
        ...contextState,
        nearest_obstacle_distance_m: dist,
      });
    }
  };

  const getCRSColor = (score: number, veto: boolean) => {
    if (veto || score < 50) return 'text-rose-400 border-rose-500/50 bg-rose-950/30';
    if (score < 85) return 'text-amber-400 border-amber-500/50 bg-amber-950/30';
    return 'text-emerald-400 border-emerald-500/50 bg-emerald-950/30';
  };

  const renderStatusBadge = (status?: CRSStatus) => {
    switch (status) {
      case 'COMPLETE':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-emerald-950/90 text-emerald-300 border border-emerald-700">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>COMPLETE</span>
          </span>
        );
      case 'PROVISIONAL':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-amber-950/90 text-amber-300 border border-amber-700">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>PROVISIONAL</span>
          </span>
        );
      case 'INCOMPLETE':
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-slate-800 text-slate-300 border border-slate-600">
            <span className="w-2 h-2 rounded-full bg-slate-400" />
            <span>INCOMPLETE</span>
          </span>
        );
      case 'INVALID':
      default:
        return (
          <span className="flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold bg-rose-950/90 text-rose-300 border border-rose-700">
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            <span>INVALID</span>
          </span>
        );
    }
  };

  const renderFindingBadge = (finding?: AnalyticalFinding) => {
    switch (finding) {
      case 'AGREEMENT':
        return (
          <span className="px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-emerald-900/60 text-emerald-300 border border-emerald-700">
            AGREEMENT
          </span>
        );
      case 'CONTRADICTION':
        return (
          <span className="px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-rose-900/60 text-rose-300 border border-rose-700 animate-pulse">
            CONTRADICTION
          </span>
        );
      case 'CONTEXT_VIOLATION':
        return (
          <span className="px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-amber-900/60 text-amber-300 border border-amber-700">
            CONTEXT_VIOLATION
          </span>
        );
      case 'NEUTRAL_JOYSTICK':
        return (
          <span className="px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-cyan-900/60 text-cyan-300 border border-cyan-700">
            NEUTRAL_JOYSTICK
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            {finding || 'INSUFFICIENT_EVIDENCE'}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Header & System Status Bar */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-indigo-500/10 border border-indigo-500/30 rounded-xl">
              <Layers className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-xl font-bold text-white tracking-wide">
                  DCRG Fusion Engine & Command Reliability Score (CRS)
                </h2>
                <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-700">
                  Phase 5
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Multi-factor cross-modal reliability scoring, directional cosine alignment, and zero-override contradiction veto filter.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700">
              <span className={`w-2 h-2 rounded-full ${isWsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
              <span className="text-xs font-mono text-slate-300">
                {isWsConnected ? 'WS Stream Active' : 'WS Disconnected'}
              </span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700 text-xs font-mono text-slate-300">
              Profile: <span className="text-indigo-400 font-bold">{fusionConfig?.scoring_config_version || 'v1.0-prototype'}</span>
            </div>
          </div>
        </div>

        {/* Aggregate Telemetry Row */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-4 border-t border-slate-800/80">
          <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
            <div className="text-xs text-slate-400">Total Fused Events</div>
            <div className="text-lg font-bold font-mono text-slate-100">
              {fusionStatus?.total_evaluations ?? 0}
            </div>
          </div>
          <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
            <div className="text-xs text-slate-400">Agreements Verified</div>
            <div className="text-lg font-bold font-mono text-emerald-400">
              {fusionStatus?.total_agreements ?? 0}
            </div>
          </div>
          <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
            <div className="text-xs text-slate-400">Contradictions Vetoed</div>
            <div className="text-lg font-bold font-mono text-rose-400">
              {fusionStatus?.total_contradictions ?? 0}
            </div>
          </div>
          <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
            <div className="text-xs text-slate-400">Mean Evaluated CRS</div>
            <div className="text-lg font-bold font-mono text-indigo-400">
              {fusionStatus?.average_crs ? `${fusionStatus.average_crs.toFixed(1)} / 100` : '--'}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Contradiction Veto Interlock Banner (If Triggered) */}
      {latestFusion?.contradiction_detected && (
        <div className="bg-rose-950/80 border-2 border-rose-600 rounded-xl p-4 shadow-lg flex items-start space-x-3.5 animate-pulse">
          <ShieldAlert className="w-6 h-6 text-rose-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-rose-200 tracking-wide uppercase">
                Zero-Override Contradiction Veto Filter Asserted
              </h3>
              <span className="text-xs font-mono font-bold text-rose-300 bg-rose-900/80 px-2 py-0.5 rounded border border-rose-600">
                CRS CLAMPED TO {latestFusion.CRS.toFixed(1)} / 30.0 MAX
              </span>
            </div>
            <p className="text-xs text-rose-300 mt-1">
              {latestFusion.contradiction_reason || 'Direct conflict between verbal command and physical actuator vector.'}
            </p>
            <p className="text-[11px] text-rose-400/90 mt-1 italic">
              Core Safety Interlock: A high numerical CRS score cannot override a direct directional contradiction. Movement authorization blocked.
            </p>
          </div>
        </div>
      )}

      {/* 3. Primary CRS Gauge & Component Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Card: Large Score Gauge & Details */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center space-x-2">
                <Gauge className="w-5 h-5 text-indigo-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Command Reliability Score
                </h3>
              </div>
              {renderStatusBadge(latestFusion?.CRS_status)}
            </div>

            {/* Score Ring Display */}
            <div className="flex flex-col items-center justify-center my-6">
              <div
                className={`relative w-44 h-44 rounded-full border-4 flex flex-col items-center justify-center shadow-2xl transition-all duration-300 ${getCRSColor(
                  latestFusion?.CRS ?? 0,
                  latestFusion?.contradiction_detected ?? false
                )}`}
              >
                <div className="text-5xl font-black font-mono tracking-tight">
                  {latestFusion ? latestFusion.CRS.toFixed(1) : '--'}
                </div>
                <div className="text-xs font-semibold uppercase tracking-widest mt-1 opacity-80">
                  / 100.0 CRS
                </div>
                {latestFusion?.recommended_state && (
                  <div className="mt-2 text-[11px] font-mono font-bold px-2.5 py-0.5 rounded bg-black/40 border border-current">
                    TARGET: {latestFusion.recommended_state}
                  </div>
                )}
              </div>
              <div className="mt-4 flex items-center space-x-2">
                {renderFindingBadge(latestFusion?.analytical_finding)}
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800 text-xs text-slate-400 space-y-1 font-mono">
            <div className="flex justify-between">
              <span>Voice Token:</span>
              <span className="text-slate-200 font-semibold">{latestFusion?.voice_command || 'None'}</span>
            </div>
            <div className="flex justify-between">
              <span>Joystick Vector:</span>
              <span className="text-slate-200 font-semibold">{latestFusion?.joystick_direction || 'None'} ({latestFusion?.joystick_intensity ? `${(latestFusion.joystick_intensity * 100).toFixed(0)}%` : '0%'})</span>
            </div>
            <div className="flex justify-between">
              <span>Evidence Completeness:</span>
              <span className="text-slate-200 font-semibold">
                {latestFusion?.evidence_completeness ? `${(latestFusion.evidence_completeness * 100).toFixed(0)}%` : '0%'}
              </span>
            </div>
          </div>
        </div>

        {/* Right 2 Columns: Multi-Factor Decomposition */}
        <div className="lg:col-span-2 bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <Sliders className="w-5 h-5 text-indigo-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Multimodal Factor Decomposition
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                Formula: CRS = 100 × (0.35·S + 0.50·M + 0.15·C)
              </span>
            </div>

            <div className="space-y-4">
              {/* Factor 1: Semantic S */}
              <div className="bg-slate-950/60 p-3.5 rounded-lg border border-slate-800/80">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-xs font-bold text-slate-300">
                    Semantic Reliability (S) <span className="text-slate-500 font-normal">W_s = 0.35</span>
                  </span>
                  <span className="text-sm font-mono font-bold text-sky-400">
                    {latestFusion ? (latestFusion.semantic_reliability * 100).toFixed(1) : 0}%
                  </span>
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-sky-500 h-full transition-all duration-300 rounded-full"
                    style={{ width: `${(latestFusion?.semantic_reliability ?? 0) * 100}%` }}
                  />
                </div>
                <div className="text-[11px] text-slate-400 mt-1.5 flex justify-between">
                  <span>Recognition Confidence: {latestFusion?.voice_command ? 'Active' : 'Unpartnered'}</span>
                  <span className="italic">S = C_whisper × (1 - 0.25·S_stress)</span>
                </div>
              </div>

              {/* Factor 2: Motor Agreement M */}
              <div className="bg-slate-950/60 p-3.5 rounded-lg border border-slate-800/80">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-xs font-bold text-slate-300">
                    Motor Agreement Factor (M) <span className="text-slate-500 font-normal">W_m = 0.50</span>
                  </span>
                  <span className="text-sm font-mono font-bold text-emerald-400">
                    {latestFusion ? (latestFusion.motor_agreement * 100).toFixed(1) : 0}%
                  </span>
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full transition-all duration-300 rounded-full"
                    style={{ width: `${(latestFusion?.motor_agreement ?? 0) * 100}%` }}
                  />
                </div>
                <div className="text-[11px] text-slate-400 mt-1.5 flex justify-between">
                  <span>
                    Cosine Sim: {latestFusion?.factors.cosine_similarity !== null && latestFusion?.factors.cosine_similarity !== undefined
                      ? latestFusion.factors.cosine_similarity.toFixed(2)
                      : 'N/A'}{' '}
                    ({latestFusion?.factors.angular_delta_deg ? `${latestFusion.factors.angular_delta_deg.toFixed(1)}°` : '0°'})
                  </span>
                  <span className="italic">M = ((1 + cos)/2) × √I_joy × Q_sync</span>
                </div>
              </div>

              {/* Factor 3: Context Consistency C */}
              <div className="bg-slate-950/60 p-3.5 rounded-lg border border-slate-800/80">
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-xs font-bold text-slate-300">
                    Contextual Consistency (C) <span className="text-slate-500 font-normal">W_c = 0.15</span>
                  </span>
                  <span className="text-sm font-mono font-bold text-purple-400">
                    {latestFusion ? (latestFusion.context_consistency * 100).toFixed(1) : 0}%
                  </span>
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-purple-500 h-full transition-all duration-300 rounded-full"
                    style={{ width: `${(latestFusion?.context_consistency ?? 0) * 100}%` }}
                  />
                </div>
                <div className="text-[11px] text-slate-400 mt-1.5 flex justify-between">
                  <span>Operating Mode: <span className="text-slate-200 font-semibold">{contextState?.operating_mode || 'NORMAL'}</span></span>
                  <span>Obstacle Buffer: {contextState?.nearest_obstacle_distance_m.toFixed(1)}m</span>
                </div>
              </div>
            </div>
          </div>

          {/* Explainability Callout */}
          <div className="mt-4 p-3 bg-slate-950/80 rounded-lg border border-slate-800 text-xs text-slate-300 font-mono">
            <span className="text-indigo-400 font-bold">Reasoning: </span>
            {latestFusion?.explanation || 'Waiting for correlated multimodal events to evaluate...'}
          </div>
        </div>
      </div>

      {/* 4. Interactive Multimodal Evaluator Sandbox */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left: Manual Test Pair Evaluator */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl">
          <div className="flex items-center space-x-2 mb-4">
            <Zap className="w-5 h-5 text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Multimodal Evaluator Sandbox
            </h3>
          </div>
          <p className="text-xs text-slate-400 mb-4">
            Simulate arbitrary voice/joystick command pairings to verify CRS scoring, temporal decay, and contradiction triggers.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-slate-400 font-mono block mb-1">Voice Command</label>
              <select
                value={evalVoiceCmd}
                onChange={(e) => setEvalVoiceCmd(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono"
              >
                <option value="FORWARD">FORWARD</option>
                <option value="BACKWARD">BACKWARD</option>
                <option value="LEFT">LEFT</option>
                <option value="RIGHT">RIGHT</option>
                <option value="STOP">STOP</option>
                <option value="UNKNOWN">UNKNOWN</option>
                <option value="UNCERTAIN">UNCERTAIN</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-400 font-mono block mb-1">
                Whisper Confidence: {(evalVoiceConf * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0.10"
                max="1.0"
                step="0.05"
                value={evalVoiceConf}
                onChange={(e) => setEvalVoiceConf(parseFloat(e.target.value))}
                className="w-full accent-indigo-500"
              />
            </div>

            <div>
              <label className="text-xs text-slate-400 font-mono block mb-1">Joystick Direction</label>
              <select
                value={evalJoyDir}
                onChange={(e) => setEvalJoyDir(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono"
              >
                <option value="FORWARD">FORWARD</option>
                <option value="BACKWARD">BACKWARD</option>
                <option value="LEFT">LEFT</option>
                <option value="RIGHT">RIGHT</option>
                <option value="CENTER">CENTER (Neutral)</option>
                <option value="FORWARD_LEFT">FORWARD_LEFT</option>
                <option value="FORWARD_RIGHT">FORWARD_RIGHT</option>
              </select>
            </div>

            <div>
              <label className="text-xs text-slate-400 font-mono block mb-1">
                Joystick Deflection: {(evalJoyInt * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={evalJoyInt}
                onChange={(e) => setEvalJoyInt(parseFloat(e.target.value))}
                className="w-full accent-emerald-500"
              />
            </div>

            <div>
              <label className="text-xs text-slate-400 font-mono block mb-1">
                Cognitive Stress Score: {(evalStress * 100).toFixed(0)}%
              </label>
              <input
                type="range"
                min="0.0"
                max="1.0"
                step="0.05"
                value={evalStress}
                onChange={(e) => setEvalStress(parseFloat(e.target.value))}
                className="w-full accent-amber-500"
              />
            </div>

            <div>
              <label className="text-xs text-slate-400 font-mono block mb-1">
                Temporal Delta: {evalDeltaMs.toFixed(0)} ms
              </label>
              <input
                type="range"
                min="0"
                max="250"
                step="5"
                value={evalDeltaMs}
                onChange={(e) => setEvalDeltaMs(parseFloat(e.target.value))}
                className="w-full accent-cyan-500"
              />
            </div>
          </div>

          <div className="mt-5 flex items-center justify-between">
            <button
              onClick={handleManualRun}
              disabled={evalLoading}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-mono font-bold tracking-wide transition-colors shadow-md disabled:opacity-50"
            >
              {evalLoading ? 'Computing CRS...' : 'Evaluate Multimodal Pair'}
            </button>
            <span className="text-[11px] text-slate-400 font-mono">
              Live updates propagate across WebSockets
            </span>
          </div>
        </div>

        {/* Right: Operational Context Management */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center space-x-2">
                <Compass className="w-5 h-5 text-indigo-400" />
                <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                  Operational Context Controls
                </h3>
              </div>
              <button
                onClick={resetContext}
                className="flex items-center space-x-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs font-mono text-slate-300 transition-colors"
                title="Reset context to nominal baseline"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset</span>
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs text-slate-400 font-mono block mb-1">
                  Active Mission Operating Mode
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(['NORMAL', 'RESTRICTED', 'PRECISION', 'EMERGENCY_STOP', 'DOCKED'] as MissionMode[]).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => handleModeChange(mode)}
                      className={`px-2.5 py-1.5 rounded-lg text-xs font-mono font-semibold border transition-all ${
                        contextState?.operating_mode === mode
                          ? 'bg-indigo-600 text-white border-indigo-400 shadow-md'
                          : 'bg-slate-950 text-slate-400 border-slate-800 hover:bg-slate-800'
                      }`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-xs text-slate-400 font-mono">
                    Nearest Obstacle Distance:
                  </label>
                  <span className="text-xs font-mono font-bold text-amber-400">
                    {contextState?.nearest_obstacle_distance_m.toFixed(1)} m
                  </span>
                </div>
                <input
                  type="range"
                  min="0.2"
                  max="10.0"
                  step="0.2"
                  value={contextState?.nearest_obstacle_distance_m || 5.0}
                  onChange={(e) => handleObstacleDistanceChange(parseFloat(e.target.value))}
                  className="w-full accent-amber-500"
                />
                <div className="flex justify-between text-[11px] text-slate-500 font-mono mt-1">
                  <span>0.2m (Hazardous)</span>
                  <span>Stopping Buffer: {contextState?.stopping_distance_threshold_m.toFixed(1)}m</span>
                  <span>10.0m (Clear)</span>
                </div>
              </div>

              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-xs text-slate-400 space-y-1 font-mono">
                <div className="flex justify-between">
                  <span>Permitted Directions:</span>
                  <span className="text-slate-200">
                    {contextState?.permitted_directions.join(', ') || 'ALL'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Kinematic Velocity Cap:</span>
                  <span className="text-slate-200">
                    {contextState?.max_admissible_linear_velocity.toFixed(1)} m/s
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800/80 text-[11px] text-slate-500 font-mono flex items-center justify-between">
            <span>Context Engine Telemetry Source: {contextState?.context_source || 'SIMULATED'}</span>
            <span className="text-emerald-400">Context Confidence: 100%</span>
          </div>
        </div>
      </div>

      {/* 5. Recent Fusion History Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Radio className="w-5 h-5 text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Recent Multimodal Fusion History
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Showing last {fusionHistory.length} evaluations
          </span>
        </div>

        {fusionHistory.length === 0 ? (
          <div className="text-center py-8 text-xs font-mono text-slate-500">
            No multimodal fusion evaluations recorded yet. Speak a voice command or deflect the joystick.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/50">
                  <th className="py-2.5 px-3">Time</th>
                  <th className="py-2.5 px-3">Voice Command</th>
                  <th className="py-2.5 px-3">Joystick Direction</th>
                  <th className="py-2.5 px-3">Factor Scores (S / M / C)</th>
                  <th className="py-2.5 px-3">CRS</th>
                  <th className="py-2.5 px-3">Finding</th>
                  <th className="py-2.5 px-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {fusionHistory.map((item) => (
                  <tr key={item.fusion_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2.5 px-3 text-slate-400">
                      {new Date(item.timestamp).toLocaleTimeString()}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="font-bold text-sky-400">{item.voice_command || 'None'}</span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className="font-bold text-emerald-400">{item.joystick_direction || 'None'}</span>
                      {item.joystick_intensity ? (
                        <span className="text-slate-500 ml-1">({(item.joystick_intensity * 100).toFixed(0)}%)</span>
                      ) : null}
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">
                      {item.semantic_reliability.toFixed(2)} / {item.motor_agreement.toFixed(2)} / {item.context_consistency.toFixed(2)}
                    </td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`font-black text-sm px-2 py-0.5 rounded ${
                          item.contradiction_detected || item.CRS < 50
                            ? 'text-rose-400 bg-rose-950/60 border border-rose-800'
                            : item.CRS < 85
                            ? 'text-amber-400 bg-amber-950/60 border border-amber-800'
                            : 'text-emerald-400 bg-emerald-950/60 border border-emerald-800'
                        }`}
                      >
                        {item.CRS.toFixed(1)}
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      {renderFindingBadge(item.analytical_finding)}
                    </td>
                    <td className="py-2.5 px-3">
                      {renderStatusBadge(item.CRS_status)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
