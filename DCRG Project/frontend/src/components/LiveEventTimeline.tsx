/**
 * DCRG Phase 8 - Live Event Timeline Widget.
 * Shows real-time chronological multi-modal events across Voice, Joystick, Sync, Fusion, and Safety.
 */

import React, { useEffect, useState } from 'react';
import { Clock, Radio, Activity, Shield, Bot, Mic, Gamepad2 } from 'lucide-react';
import { fetchLiveTimeline } from '../services/api';
import type { AuditLogEntry } from '../types';

export const LiveEventTimeline: React.FC = () => {
  const [events, setEvents] = useState<AuditLogEntry[]>([]);

  useEffect(() => {
    fetchLiveTimeline(15).then((data) => {
      if (data) setEvents(data);
    });
    const interval = window.setInterval(() => {
      fetchLiveTimeline(15).then((data) => {
        if (data) setEvents(data);
      });
    }, 2500);
    return () => window.clearInterval(interval);
  }, []);

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'VOICE':
        return <Mic className="w-3 h-3 text-purple-400" />;
      case 'JOYSTICK':
        return <Gamepad2 className="w-3 h-3 text-blue-400" />;
      case 'SYNC':
        return <Radio className="w-3 h-3 text-amber-400" />;
      case 'FUSION':
        return <Activity className="w-3 h-3 text-emerald-400" />;
      case 'SAFETY':
        return <Shield className="w-3 h-3 text-cyan-400" />;
      case 'SIMULATION':
        return <Bot className="w-3 h-3 text-indigo-400" />;
      default:
        return <Clock className="w-3 h-3 text-slate-400" />;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 shadow-lg text-left space-y-3">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
          <Clock className="w-4 h-4 text-cyan-400" />
          Live Event Timeline Stream
        </h3>
        <span className="text-[10px] text-slate-500 font-mono">Auto-sync 2.5s</span>
      </div>

      <div className="space-y-1.5 max-h-48 overflow-y-auto font-mono text-xs pr-1">
        {events.length === 0 ? (
          <p className="text-slate-500 italic text-center py-4 text-xs">Waiting for events...</p>
        ) : (
          events.map((ev) => {
            const timeStr = ev.iso_time ? ev.iso_time.split('T')[1]?.replace('Z', '') : '';
            return (
              <div
                key={ev.id}
                className="flex items-center justify-between p-1.5 rounded bg-slate-950/60 border border-slate-800/80 hover:bg-slate-800/40 transition"
              >
                <div className="flex items-center gap-2 truncate">
                  {getCategoryIcon(ev.category)}
                  <span className="text-[10px] text-slate-400">{timeStr}</span>
                  <span className="px-1.5 py-0.2 rounded bg-slate-800 text-[10px] font-bold text-slate-300">
                    {ev.category}
                  </span>
                  <span className="font-semibold text-slate-200 truncate">
                    {ev.command || 'EVENT'}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 shrink-0 text-[10px]">
                  {ev.crs !== null && ev.crs !== undefined && (
                    <span className="text-emerald-400 font-bold">CRS: {ev.crs.toFixed(0)}</span>
                  )}
                  {ev.safety_state && (
                    <span
                      className={`px-1.5 py-0.2 rounded font-bold ${
                        ev.safety_state === 'GREEN'
                          ? 'text-emerald-400 bg-emerald-950/80'
                          : ev.safety_state === 'YELLOW'
                          ? 'text-amber-400 bg-amber-950/80'
                          : 'text-rose-400 bg-rose-950/80'
                      }`}
                    >
                      {ev.safety_state}
                    </span>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

