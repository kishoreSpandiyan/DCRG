import React, { useState } from 'react';
import {
  Shield,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Octagon,
  RotateCcw,
  Check,
  X,
  Radio,
  Server,
  Lock,
} from 'lucide-react';
import { useSafetyStream } from '../hooks/useSafetyStream';
import type {
  AuthorizationState,
  ConfirmationAction,
} from '../types';

export const SafetyDashboardPanel: React.FC = () => {
  const {
    safetyStatus,
    latestDecision,
    safetyHistory,
    pendingConfirmations,
    gatewayHistory,
    isWsConnected,
    confirmDecision,
    triggerEStop,
    resetEStop,
  } = useSafetyStream();

  const [resetPin, setResetPin] = useState<string>('1234');
  const [resetLoading, setResetLoading] = useState<boolean>(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  const activeState = safetyStatus?.active_state || 'GREEN';
  const isLatched = safetyStatus?.is_emergency_latched || false;

  const handleEStopClick = async () => {
    await triggerEStop('SOFTWARE_UI', 'Operator pressed manual emergency stop on dashboard');
  };

  const handleResetSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetLoading(true);
    setResetMessage(null);
    const res = await resetEStop(resetPin, 'OP-DASHBOARD');
    if (res && res.status === 'unlatched') {
      setResetMessage('Emergency stop successfully reset.');
    } else {
      setResetMessage('Reset rejected: Invalid authorization PIN.');
    }
    setResetLoading(false);
  };

  const handleConfirmAction = async (decisionId: string, action: ConfirmationAction) => {
    await confirmDecision(decisionId, action, 'OP-DASHBOARD');
  };

  const renderStateBanner = (state: AuthorizationState) => {
    switch (state) {
      case 'EMERGENCY':
        return (
          <div className="bg-rose-950 border-2 border-rose-500 rounded-xl p-5 shadow-2xl flex flex-col md:flex-row items-center justify-between gap-4 animate-pulse">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-rose-600 rounded-xl shadow-lg animate-bounce">
                <Octagon className="w-8 h-8 text-white" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-xl font-black text-rose-100 tracking-wider uppercase">
                    EMERGENCY STOP ENGAGED – ALL MOTION LOCKED OUT
                  </h2>
                  <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-black text-rose-400 border border-rose-600">
                    LATCHED
                  </span>
                </div>
                <p className="text-xs text-rose-300 mt-1">
                  Immediate hardware-simulated interrupt asserted. All pending commands dropped. Independent reset required.
                </p>
              </div>
            </div>
            <div className="text-xs font-mono font-bold text-rose-200 bg-rose-900/60 px-4 py-2 rounded-lg border border-rose-600">
              DISPATCH OVERRIDE: ACTIVE
            </div>
          </div>
        );
      case 'RED':
        return (
          <div className="bg-rose-950/70 border border-rose-700 rounded-xl p-5 shadow-xl flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-rose-900/60 border border-rose-700 rounded-xl">
                <ShieldAlert className="w-7 h-7 text-rose-400" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-lg font-bold text-rose-200 tracking-wide uppercase">
                    STATE: RED – MOVEMENT REJECTED & PROHIBITED
                  </h2>
                </div>
                <p className="text-xs text-rose-300 mt-0.5">
                  Command rejected due to contradiction veto, low CRS (&lt; 50), sensor fault, or environmental boundary violation.
                </p>
              </div>
            </div>
            <div className="px-3.5 py-1.5 rounded-lg bg-rose-900/80 border border-rose-600 text-xs font-mono font-bold text-rose-200">
              GATEWAY BLOCKED
            </div>
          </div>
        );
      case 'YELLOW':
        return (
          <div className="bg-amber-950/70 border border-amber-600 rounded-xl p-5 shadow-xl flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-amber-900/60 border border-amber-600 rounded-xl">
                <AlertTriangle className="w-7 h-7 text-amber-400" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-lg font-bold text-amber-200 tracking-wide uppercase">
                    STATE: YELLOW – HOLD PENDING HUMAN CONFIRMATION
                  </h2>
                  <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-amber-900 text-amber-300 border border-amber-700 animate-pulse">
                    HOLD ACTIVE
                  </span>
                </div>
                <p className="text-xs text-amber-300 mt-0.5">
                  Command held in verification buffer (50 &le; CRS &lt; 85 or unpartnered evidence). Explicit operator action required.
                </p>
              </div>
            </div>
            <div className="px-3.5 py-1.5 rounded-lg bg-amber-900/80 border border-amber-600 text-xs font-mono font-bold text-amber-200">
              AWAITING CONFIRMATION
            </div>
          </div>
        );
      case 'GREEN':
      default:
        return (
          <div className="bg-emerald-950/60 border border-emerald-600/80 rounded-xl p-5 shadow-xl flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-emerald-900/60 border border-emerald-600 rounded-xl">
                <ShieldCheck className="w-7 h-7 text-emerald-400" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-lg font-bold text-emerald-200 tracking-wide uppercase">
                    STATE: GREEN – FULLY AUTHORIZED FOR SIMULATION
                  </h2>
                </div>
                <p className="text-xs text-emerald-300 mt-0.5">
                  CRS &ge; 85, evidence complete, zero contradiction, operating boundaries clear. Motion primitive authorized.
                </p>
              </div>
            </div>
            <div className="px-3.5 py-1.5 rounded-lg bg-emerald-900/80 border border-emerald-600 text-xs font-mono font-bold text-emerald-200">
              SIMULATION READY
            </div>
          </div>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Header & Live Safety State Banner */}
      <div className="space-y-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-xl backdrop-blur-md flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-3 bg-indigo-500/10 border border-indigo-500/30 rounded-xl">
              <Shield className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-xl font-bold text-white tracking-wide">
                  Tiered Safety Authorization Engine
                </h2>
                <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-indigo-950 text-indigo-300 border border-indigo-700">
                  Phase 6
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Deterministic 4-tier state machine (GREEN / YELLOW / RED / EMERGENCY) governing simulated kinematic dispatch.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700">
              <span className={`w-2 h-2 rounded-full ${isWsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'}`} />
              <span className="text-xs font-mono text-slate-300">
                {isWsConnected ? 'Safety WS Stream Active' : 'Safety WS Disconnected'}
              </span>
            </div>
            <div className="px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700 text-xs font-mono text-slate-300">
              Green Threshold: <span className="text-emerald-400 font-bold">&ge; {safetyStatus?.green_threshold || 85} CRS</span>
            </div>
          </div>
        </div>

        {/* Primary State Banner */}
        {renderStateBanner(activeState)}
      </div>

      {/* 2. Emergency Stop Controls & Latch Reset Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Massive E-Stop Button */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col items-center justify-center text-center">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
            Independent Emergency Stop Circuit
          </h3>
          <button
            onClick={handleEStopClick}
            className={`w-40 h-40 rounded-full border-4 flex flex-col items-center justify-center shadow-2xl transition-transform active:scale-95 ${isLatched
                ? 'bg-rose-700 border-rose-400 text-white animate-pulse'
                : 'bg-rose-600 hover:bg-rose-500 border-rose-400 text-white'
              }`}
          >
            <Octagon className="w-12 h-12 mb-1" />
            <span className="text-sm font-black tracking-wider uppercase">
              {isLatched ? 'E-STOP LATCHED' : 'EMERGENCY STOP'}
            </span>
            <span className="text-[10px] font-mono mt-0.5 opacity-90">HALT ALL MOTION</span>
          </button>
          <p className="text-[11px] text-slate-500 font-mono mt-3 max-w-xs">
            Software prototype interlock. Immediately commands zero velocity and locks out subsequent authorization.
          </p>
        </div>

        {/* E-Stop Reset & Credential Authorization Form */}
        <div className="lg:col-span-2 bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl flex flex-col justify-between">
          <div>
            <div className="flex items-center space-x-2 mb-2">
              <Lock className="w-5 h-5 text-indigo-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Authorized Emergency Stop Reset Workflow
              </h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              To recover from an Emergency Stop latch, an operator must provide valid credentials. Default prototype PIN: <code className="text-indigo-400 font-bold font-mono">1234</code>.
            </p>

            <form onSubmit={handleResetSubmit} className="space-y-3">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-mono text-slate-400 block mb-1">
                    Authorization PIN
                  </label>
                  <input
                    type="password"
                    value={resetPin}
                    onChange={(e) => setResetPin(e.target.value)}
                    placeholder="Enter reset PIN (e.g. 1234)"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-slate-200"
                    disabled={!isLatched}
                  />
                </div>
                <div className="flex items-end">
                  <button
                    type="submit"
                    disabled={!isLatched || resetLoading}
                    className="w-full py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white font-mono font-bold text-xs rounded-lg transition-colors flex items-center justify-center space-x-1.5 shadow-md"
                  >
                    <RotateCcw className="w-4 h-4" />
                    <span>{resetLoading ? 'Authorizing...' : 'Authorize Safety Reset'}</span>
                  </button>
                </div>
              </div>

              {resetMessage && (
                <div className={`text-xs font-mono p-2.5 rounded-lg border ${resetMessage.includes('successfully')
                    ? 'bg-emerald-950/60 border-emerald-700 text-emerald-300'
                    : 'bg-rose-950/60 border-rose-700 text-rose-300'
                  }`}>
                  {resetMessage}
                </div>
              )}
            </form>
          </div>

          <div className="pt-3 border-t border-slate-800 text-[11px] text-slate-500 font-mono flex items-center justify-between">
            <span>Safety State: {isLatched ? 'LATCHED (Command Lockout Active)' : 'UNLATCHED (Nominal)'}</span>
            <span>Latest: {latestDecision ? `${latestDecision.authorization_decision} (${latestDecision.requested_command || 'STOP'})` : 'None'}</span>
            <span>Total Emergencies: {safetyStatus?.total_emergency || 0}</span>
          </div>
        </div>
      </div>

      {/* 3. Pending Human Confirmations Queue (YELLOW State) */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Human Confirmation Queue (YELLOW Holds)
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Pending Actions: {pendingConfirmations.length}
          </span>
        </div>

        {pendingConfirmations.length === 0 ? (
          <div className="text-center py-6 text-xs font-mono text-slate-500 bg-slate-950/40 rounded-lg border border-slate-800/60">
            No commands currently on hold. Commands with CRS &ge; 85 are automatically dispatched to simulation.
          </div>
        ) : (
          <div className="space-y-3">
            {pendingConfirmations.map((pending) => (
              <div
                key={pending.decision_id}
                className="bg-slate-950 p-4 rounded-xl border border-amber-600/80 shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs font-mono font-bold bg-amber-950 text-amber-300 border border-amber-700 px-2 py-0.5 rounded">
                      HOLD
                    </span>
                    <span className="text-sm font-black font-mono text-white">
                      COMMAND: {pending.requested_command || 'STOP'}
                    </span>
                    <span className="text-xs font-mono text-slate-400">
                      (CRS: <span className="text-amber-400 font-bold">{pending.crs_score?.toFixed(1) || '--'}</span>/100)
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 font-mono">
                    {pending.reason}
                  </p>
                  <p className="text-[11px] text-slate-500 font-mono">
                    Decision ID: {pending.decision_id} • Hold Timeout: 5000ms
                  </p>
                </div>

                <div className="flex items-center space-x-2 shrink-0">
                  <button
                    onClick={() => handleConfirmAction(pending.decision_id, 'CONFIRM')}
                    className="flex items-center space-x-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold rounded-lg transition-colors shadow-md"
                  >
                    <Check className="w-4 h-4" />
                    <span>CONFIRM</span>
                  </button>
                  <button
                    onClick={() => handleConfirmAction(pending.decision_id, 'REJECT')}
                    className="flex items-center space-x-1.5 px-4 py-2 bg-rose-700 hover:bg-rose-600 text-white text-xs font-mono font-bold rounded-lg transition-colors shadow-md"
                  >
                    <X className="w-4 h-4" />
                    <span>REJECT</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 4. Simulated Command Gateway Execution Log */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Server className="w-5 h-5 text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Simulated Command Gateway Execution Audit
            </h3>
          </div>
          <span className="text-xs font-mono text-emerald-400 font-bold">
            Simulation Safeguard Active (No Physical Actuators)
          </span>
        </div>

        {gatewayHistory.length === 0 ? (
          <div className="text-center py-6 text-xs font-mono text-slate-500 bg-slate-950/40 rounded-lg border border-slate-800/60">
            No simulated gateway commands executed yet. Authorized commands will appear here.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/50">
                  <th className="py-2.5 px-3">Time</th>
                  <th className="py-2.5 px-3">Command</th>
                  <th className="py-2.5 px-3">Gateway Status</th>
                  <th className="py-2.5 px-3">Execution Rationale</th>
                  <th className="py-2.5 px-3">Auth Token (Signature)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {gatewayHistory.map((rec) => (
                  <tr key={rec.execution_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2 px-3 text-slate-400">
                      {new Date(rec.timestamp_ms).toLocaleTimeString()}
                    </td>
                    <td className="py-2 px-3 font-bold text-slate-100">{rec.command}</td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${rec.accepted
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-700'
                            : 'bg-rose-950 text-rose-300 border border-rose-700'
                          }`}
                      >
                        {rec.accepted ? 'ACCEPTED' : 'REJECTED'}
                      </span>
                    </td>
                    <td className="py-2 px-3 text-slate-300">{rec.reason}</td>
                    <td className="py-2 px-3 text-slate-500 truncate max-w-xs">
                      {rec.auth_token ? rec.auth_token.slice(0, 16) + '...' : 'None'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. Recent Safety Decisions History Table */}
      <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-5 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-2">
            <Radio className="w-5 h-5 text-indigo-400" />
            <h3 className="text-sm font-bold text-white uppercase tracking-wider">
              Recent Safety Authorization Decisions
            </h3>
          </div>
          <span className="text-xs font-mono text-slate-400">
            Total Decisions Evaluated: {safetyStatus?.total_decisions || 0}
          </span>
        </div>

        {safetyHistory.length === 0 ? (
          <div className="text-center py-6 text-xs font-mono text-slate-500">
            No safety decisions recorded yet.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/50">
                  <th className="py-2.5 px-3">Time</th>
                  <th className="py-2.5 px-3">Requested</th>
                  <th className="py-2.5 px-3">State</th>
                  <th className="py-2.5 px-3">Decision</th>
                  <th className="py-2.5 px-3">CRS</th>
                  <th className="py-2.5 px-3">Authorized Command</th>
                  <th className="py-2.5 px-3">Safety Justification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {safetyHistory.map((item) => (
                  <tr key={item.decision_id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-2 px-3 text-slate-400">
                      {new Date(item.timestamp_ms).toLocaleTimeString()}
                    </td>
                    <td className="py-2 px-3 font-bold text-sky-400">
                      {item.requested_command || 'None'}
                    </td>
                    <td className="py-2 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-bold ${item.authorization_state === 'GREEN'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-700'
                            : item.authorization_state === 'YELLOW'
                              ? 'bg-amber-950 text-amber-300 border border-amber-700'
                              : item.authorization_state === 'EMERGENCY'
                                ? 'bg-rose-950 text-rose-300 border border-rose-500 font-black'
                                : 'bg-rose-950 text-rose-300 border border-rose-800'
                          }`}
                      >
                        {item.authorization_state}
                      </span>
                    </td>
                    <td className="py-2 px-3 font-semibold text-slate-200">
                      {item.authorization_decision}
                    </td>
                    <td className="py-2 px-3 font-bold text-indigo-400">
                      {item.crs_score ? item.crs_score.toFixed(1) : '--'}
                    </td>
                    <td className="py-2 px-3 font-bold text-emerald-400">
                      {item.authorized_command || '--'}
                    </td>
                    <td className="py-2 px-3 text-slate-300 max-w-sm truncate" title={item.reason}>
                      {item.reason}
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
