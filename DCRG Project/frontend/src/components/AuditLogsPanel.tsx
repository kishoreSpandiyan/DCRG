/**
 * DCRG Phase 8 - Persistent Audit Logs & Forensic History Panel (Section 5).
 * Connects to SQLite persistent storage with multi-criteria filtering and JSON/CSV export.
 */

import React, { useEffect, useState, useCallback } from 'react';
import {
  FileText,
  Download,
  RefreshCw,
} from 'lucide-react';
import { fetchSystemLogs, getExportLogsUrl } from '../services/api';
import type { AuditLogEntry, AuditLogQueryFilter } from '../types';

export const AuditLogsPanel: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [totalRecords, setTotalRecords] = useState(0);
  const [loading, setLoading] = useState(false);

  // Filters
  const [category, setCategory] = useState<string>('ALL');
  const [safetyState, setSafetyState] = useState<string>('ALL');
  const [executionResult, setExecutionResult] = useState<string>('ALL');
  const [command, setCommand] = useState<string>('');
  const [limit, setLimit] = useState<number>(50);

  const loadLogs = useCallback(async () => {
    setLoading(true);
    const filter: AuditLogQueryFilter = {
      category: category !== 'ALL' ? category : undefined,
      safety_state: safetyState !== 'ALL' ? safetyState : undefined,
      execution_result: executionResult !== 'ALL' ? executionResult : undefined,
      command: command.trim() ? command.trim() : undefined,
      limit,
    };
    try {
      const res = await fetchSystemLogs(filter);
      setLogs(res.logs);
      setTotalRecords(res.total_records);
    } catch {
      // Ignored
    } finally {
      setLoading(false);
    }
  }, [category, safetyState, executionResult, command, limit]);

  useEffect(() => {
    loadLogs();
  }, [loadLogs]);

  const getBadgeStyle = (state?: string | null) => {
    switch (state) {
      case 'GREEN':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
      case 'YELLOW':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      case 'RED':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/40';
      case 'EMERGENCY':
        return 'bg-red-600/30 text-red-400 border-red-500 font-bold';
      default:
        return 'bg-slate-800 text-slate-400 border-slate-700';
    }
  };

  const getResultStyle = (res?: string | null) => {
    switch (res) {
      case 'EXECUTED':
      case 'AUTHORIZED':
        return 'text-emerald-400';
      case 'HELD':
        return 'text-amber-400';
      case 'REJECTED':
      case 'CANCELLED':
        return 'text-rose-400';
      case 'EMERGENCY_STOPPED':
        return 'text-red-500 font-bold';
      default:
        return 'text-slate-400';
    }
  };

  const handleExport = (format: 'json' | 'csv') => {
    const filter: AuditLogQueryFilter = {
      category: category !== 'ALL' ? category : undefined,
      safety_state: safetyState !== 'ALL' ? safetyState : undefined,
      execution_result: executionResult !== 'ALL' ? executionResult : undefined,
      command: command.trim() ? command.trim() : undefined,
    };
    const url = getExportLogsUrl(format, filter);
    window.open(url, '_blank');
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-5 text-left">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-blue-500/10 rounded-lg border border-blue-500/20">
            <FileText className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
              Forensic Audit Logs & History
              <span className="text-xs px-2 py-0.5 rounded-full bg-blue-900/60 text-blue-300 border border-blue-700 font-mono">
                SQLite Persistent
              </span>
            </h2>
            <p className="text-sm text-slate-400">
              Immutable chronological records across Voice, Stick, Sync, Fusion, Safety, and Simulation
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Export CSV */}
          <button
            onClick={() => handleExport('csv')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono font-medium border border-slate-700 transition"
          >
            <Download className="w-3.5 h-3.5 text-cyan-400" /> Export CSV
          </button>

          {/* Export JSON */}
          <button
            onClick={() => handleExport('json')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono font-medium border border-slate-700 transition"
          >
            <Download className="w-3.5 h-3.5 text-purple-400" /> Export JSON
          </button>

          {/* Refresh */}
          <button
            onClick={loadLogs}
            disabled={loading}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Refresh logs"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="p-4 bg-slate-950/60 border border-slate-800 rounded-xl grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3 text-xs font-mono">
        {/* Category Filter */}
        <div>
          <label className="text-slate-400 block mb-1">Category</label>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Categories</option>
            <option value="VOICE">VOICE</option>
            <option value="JOYSTICK">JOYSTICK</option>
            <option value="SYNC">SYNC</option>
            <option value="FUSION">FUSION</option>
            <option value="SAFETY">SAFETY</option>
            <option value="SIMULATION">SIMULATION</option>
            <option value="CONFIG">CONFIG</option>
          </select>
        </div>

        {/* Safety State Filter */}
        <div>
          <label className="text-slate-400 block mb-1">Safety State</label>
          <select
            value={safetyState}
            onChange={(e) => setSafetyState(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All States</option>
            <option value="GREEN">GREEN</option>
            <option value="YELLOW">YELLOW</option>
            <option value="RED">RED</option>
            <option value="EMERGENCY">EMERGENCY</option>
          </select>
        </div>

        {/* Execution Result Filter */}
        <div>
          <label className="text-slate-400 block mb-1">Execution Result</label>
          <select
            value={executionResult}
            onChange={(e) => setExecutionResult(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="ALL">All Outcomes</option>
            <option value="EXECUTED">EXECUTED</option>
            <option value="HELD">HELD</option>
            <option value="REJECTED">REJECTED</option>
            <option value="EMERGENCY_STOPPED">EMERGENCY_STOPPED</option>
          </select>
        </div>

        {/* Command Primitive Filter */}
        <div>
          <label className="text-slate-400 block mb-1">Command Search</label>
          <div className="relative">
            <input
              type="text"
              placeholder="e.g. FORWARD, LEFT"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500 uppercase"
            />
          </div>
        </div>

        {/* Record Limit */}
        <div>
          <label className="text-slate-400 block mb-1">Display Limit</label>
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value={25}>25 Events</option>
            <option value={50}>50 Events</option>
            <option value={100}>100 Events</option>
            <option value={200}>200 Events</option>
          </select>
        </div>
      </div>

      {/* Metadata status line */}
      <div className="flex items-center justify-between text-xs font-mono text-slate-400">
        <span>
          Showing <strong className="text-slate-200">{logs.length}</strong> of{' '}
          <strong className="text-slate-200">{totalRecords}</strong> total logged forensic records
        </span>
        <span>Storage: <code className="text-cyan-400">dcrg_audit.db (SQLite)</code></span>
      </div>

      {/* Audit Log Table */}
      <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/50">
        <div className="overflow-x-auto max-h-[460px]">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 sticky top-0">
              <tr>
                <th className="px-3 py-2.5">Time (UTC)</th>
                <th className="px-3 py-2.5">Category</th>
                <th className="px-3 py-2.5">Command</th>
                <th className="px-3 py-2.5">Safety State</th>
                <th className="px-3 py-2.5">Result</th>
                <th className="px-3 py-2.5">CRS</th>
                <th className="px-3 py-2.5">Forensic Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500 italic">
                    {loading ? 'Querying forensic database...' : 'No audit records match the selected filters.'}
                  </td>
                </tr>
              ) : (
                logs.map((log) => {
                  const date = new Date(log.timestamp_ms);
                  const timeFormatted = `${date.toTimeString().split(' ')[0]}.${date
                    .getMilliseconds()
                    .toString()
                    .padStart(3, '0')}`;
                  return (
                    <tr key={log.id} className="hover:bg-slate-800/30 transition">
                      <td className="px-3 py-2 text-slate-400 whitespace-nowrap">{timeFormatted}</td>
                      <td className="px-3 py-2">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                          {log.category}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-semibold text-white">
                        {log.command || '—'}
                      </td>
                      <td className="px-3 py-2">
                        {log.safety_state ? (
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getBadgeStyle(
                              log.safety_state
                            )}`}
                          >
                            {log.safety_state}
                          </span>
                        ) : (
                          <span className="text-slate-600">—</span>
                        )}
                      </td>
                      <td className="px-3 py-2 font-semibold">
                        <span className={getResultStyle(log.execution_result)}>
                          {log.execution_result || '—'}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-slate-300">
                        {log.crs !== null && log.crs !== undefined ? `${log.crs.toFixed(1)}` : '—'}
                      </td>
                      <td className="px-3 py-2 text-slate-400 max-w-sm truncate" title={JSON.stringify(log.details)}>
                        {Object.keys(log.details || {}).length > 0
                          ? JSON.stringify(log.details)
                          : log.details_json || '—'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
