/**
 * DCRG Phase 8 - System Configuration Panel (Section 6).
 * Controls Sync window, Joystick deadzone, Voice threshold, CRS weights,
 * Safety thresholds, and Simulation speed with real-time validation and defaults.
 */

import React, { useEffect, useState } from 'react';
import {
  Sliders,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Save,
  FlaskConical,
} from 'lucide-react';
import { fetchSystemConfig, updateSystemConfig, resetSystemConfig } from '../services/api';

export const ConfigurationPanel: React.FC = () => {
  const [form, setForm] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const loadConfig = async () => {
    try {
      const res = await fetchSystemConfig();
      if (res) {
        setForm(res.parameters);
      }
    } catch {
      // Ignored
    }
  };

  useEffect(() => {
    loadConfig();
  }, []);

  const handleChange = (key: string, val: number) => {
    setForm((prev) => ({ ...prev, [key]: val }));
    setMessage(null);
  };

  // Validation Checks
  const crsSum = (form.crs_weight_semantic || 0) + (form.crs_weight_motor || 0) + (form.crs_weight_context || 0);
  const isCrsSumValid = Math.abs(crsSum - 1.0) <= 0.005;
  const isThresholdValid = (form.safety_yellow_threshold || 0) < (form.safety_green_threshold || 100);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isCrsSumValid) {
      setMessage({
        type: 'error',
        text: `CRS weights must sum to 1.00 (Current: ${crsSum.toFixed(3)})`,
      });
      return;
    }
    if (!isThresholdValid) {
      setMessage({
        type: 'error',
        text: 'Safety YELLOW threshold must be strictly less than GREEN threshold.',
      });
      return;
    }

    setLoading(true);
    try {
      const res = await updateSystemConfig(form, 'OP-PRIMARY', 'Operator adjusted settings in UI');
      setMessage({ type: 'success', text: res.message });
      await loadConfig();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Configuration update failed' });
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!window.confirm('Reset all system configurations to factory defaults?')) return;
    setLoading(true);
    try {
      const res = await resetSystemConfig('OP-PRIMARY');
      setMessage({ type: 'success', text: res.message });
      await loadConfig();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Reset failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6 text-left">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-cyan-500/10 rounded-lg border border-cyan-500/20">
            <Sliders className="w-6 h-6 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
              System Configuration & Operating Parameters
              <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-900/60 text-cyan-300 border border-cyan-700 font-mono">
                Validated
              </span>
            </h2>
            <p className="text-sm text-slate-400">
              Deterministic threshold management, CRS factor weighting, and physical simulation scaling
            </p>
          </div>
        </div>

        <button
          onClick={handleReset}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono font-medium border border-slate-700 transition"
        >
          <RotateCcw className="w-3.5 h-3.5 text-cyan-400" /> Reset to Defaults
        </button>
      </div>

      {/* Status Messages */}
      {message && (
        <div
          className={`p-3 rounded-lg border text-xs font-mono flex items-center gap-2 ${
            message.type === 'success'
              ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
              : 'bg-rose-950/60 border-rose-800 text-rose-300'
          }`}
        >
          {message.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          ) : (
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
          )}
          <span>{message.text}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section 1: Synchronization & Inputs */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800 pb-2">
            Multi-Modal Synchronization & Input Filters
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
            {/* Sync Window */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-semibold">Sync Window (ms)</span>
                <span className="text-[10px] text-slate-500">Default: 150 ms</span>
              </div>
              <input
                type="number"
                min={50}
                max={500}
                step={10}
                value={form.sync_window_ms || 150}
                onChange={(e) => handleChange('sync_window_ms', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                Acoustic & motor temporal correlation matching bound [50 - 500 ms].
              </p>
            </div>

            {/* Joystick Deadzone */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-semibold">Joystick Radial Deadzone</span>
                <span className="text-[10px] text-slate-500">Default: 0.08</span>
              </div>
              <input
                type="number"
                min={0.01}
                max={0.4}
                step={0.01}
                value={form.joystick_deadzone || 0.08}
                onChange={(e) => handleChange('joystick_deadzone', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                Radial noise threshold below which stick is neutral [0.01 - 0.40].
              </p>
            </div>

            {/* Voice Confidence */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-semibold">Voice Confidence Floor</span>
                <span className="text-[10px] text-slate-500">Default: 0.60</span>
              </div>
              <input
                type="number"
                min={0.1}
                max={1.0}
                step={0.05}
                value={form.voice_confidence_threshold || 0.6}
                onChange={(e) => handleChange('voice_confidence_threshold', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                Minimum Whisper acoustic confidence for speech admissibility.
              </p>
            </div>
          </div>
        </div>

        {/* Section 2: CRS Factor Weights */}
        <div className="space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Command Reliability Score (CRS) Weights
            </h3>
            <span
              className={`text-xs font-mono font-bold px-2 py-0.5 rounded ${
                isCrsSumValid
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800'
                  : 'bg-rose-950 text-rose-400 border border-rose-800 animate-pulse'
              }`}
            >
              Weight Sum: {crsSum.toFixed(3)} / 1.000
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
            {/* Ws: Semantic Weight */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-semibold">Semantic Weight (Ws)</span>
                <span className="text-[10px] text-slate-500">Default: 0.35</span>
              </div>
              <input
                type="number"
                min={0.0}
                max={1.0}
                step={0.05}
                value={form.crs_weight_semantic ?? 0.35}
                onChange={(e) => handleChange('crs_weight_semantic', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                Speech recognition accuracy & stress factor contribution.
              </p>
            </div>

            {/* Wm: Motor Agreement Weight */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-semibold">Motor Agreement (Wm)</span>
                <span className="text-[10px] text-slate-500">Default: 0.50</span>
              </div>
              <input
                type="number"
                min={0.0}
                max={1.0}
                step={0.05}
                value={form.crs_weight_motor ?? 0.5}
                onChange={(e) => handleChange('crs_weight_motor', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                Directional vector alignment cos(Δθ) contribution.
              </p>
            </div>

            {/* Wc: Context Consistency Weight */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-slate-300 font-semibold">Context Consistency (Wc)</span>
                <span className="text-[10px] text-slate-500">Default: 0.15</span>
              </div>
              <input
                type="number"
                min={0.0}
                max={1.0}
                step={0.05}
                value={form.crs_weight_context ?? 0.15}
                onChange={(e) => handleChange('crs_weight_context', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                Environmental & mission constraint compliance contribution.
              </p>
            </div>
          </div>
        </div>

        {/* Section 3: Tiered Safety Thresholds & Simulation */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 border-b border-slate-800 pb-2">
            Safety Authorization Gate & Simulation Parameters
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs font-mono">
            {/* Green Threshold */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-emerald-400 font-semibold">GREEN Threshold</span>
                <span className="text-[10px] text-slate-500">Default: 85.0</span>
              </div>
              <input
                type="number"
                min={50.0}
                max={100.0}
                step={1.0}
                value={form.safety_green_threshold || 85.0}
                onChange={(e) => handleChange('safety_green_threshold', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                CRS score required for automatic simulation dispatch [50 - 100].
              </p>
            </div>

            {/* Yellow Threshold */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-amber-400 font-semibold">YELLOW Threshold</span>
                <span className="text-[10px] text-slate-500">Default: 50.0</span>
              </div>
              <input
                type="number"
                min={10.0}
                max={80.0}
                step={1.0}
                value={form.safety_yellow_threshold || 50.0}
                onChange={(e) => handleChange('safety_yellow_threshold', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                CRS score floor for hold-pending-confirmation [10 - 80].
              </p>
            </div>

            {/* Simulation Speed */}
            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-cyan-400 font-semibold">Simulation Speed Multiplier</span>
                <span className="text-[10px] text-slate-500">Default: 1.0x</span>
              </div>
              <input
                type="number"
                min={0.1}
                max={5.0}
                step={0.1}
                value={form.simulation_speed || 1.0}
                onChange={(e) => handleChange('simulation_speed', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-slate-500">
                Kinematic physics time scale factor [0.1x to 5.0x].
              </p>
            </div>
          </div>
        </div>

        {/* Section 4: Experimental Parameters */}
        <div className="p-4 bg-amber-950/20 border border-amber-800/50 rounded-xl space-y-3">
          <div className="flex items-center gap-2 text-amber-400 font-mono text-xs font-bold">
            <FlaskConical className="w-4 h-4" />
            <span>EXPERIMENTAL / UNVALIDATED PARAMETERS</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
            <div className="space-y-1.5">
              <label className="text-slate-300 font-semibold">Prosody Stress Damping (Beta)</label>
              <input
                type="number"
                min={0.0}
                max={1.0}
                step={0.05}
                value={form.prosody_stress_damping ?? 0.25}
                onChange={(e) => handleChange('prosody_stress_damping', Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-slate-100 font-mono"
              />
              <p className="text-[10px] text-amber-300/80">
                Acoustic stress penalty coefficient. Marked EXPERIMENTAL pending clinical validation.
              </p>
            </div>
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={loading || !isCrsSumValid || !isThresholdValid}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-mono text-xs font-bold tracking-wide transition shadow-lg shadow-cyan-900/30"
          >
            <Save className="w-4 h-4" />
            {loading ? 'Applying Changes...' : 'Save & Propagate Configuration'}
          </button>
        </div>
      </form>
    </div>
  );
};
