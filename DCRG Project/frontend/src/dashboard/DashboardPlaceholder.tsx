import React from 'react';
import { Network, Mic, Waves, ShieldCheck, Gamepad2, Database } from 'lucide-react';

const MODULES = [
  {
    name: 'Voice Engine',
    desc: 'Spoken command capture & Faster-Whisper transcription',
    phase: 'Phase 3',
    icon: Mic,
    color: 'text-indigo-400',
  },
  {
    name: 'Prosody Engine',
    desc: 'Acoustic pitch, stress & Librosa signal analysis',
    phase: 'Phase 3',
    icon: Waves,
    color: 'text-sky-400',
  },
  {
    name: 'Actuator Engine',
    desc: 'USB/Bluetooth joystick & Gamepad API input sampling',
    phase: 'Phase 2',
    icon: Gamepad2,
    color: 'text-emerald-400',
  },
  {
    name: 'Fusion Engine (CRS)',
    desc: 'Multi-modal cross-correlation & Dynamic Reliability Graph',
    phase: 'Phase 5',
    icon: Network,
    color: 'text-amber-400',
  },
  {
    name: 'Safety Engine',
    desc: 'Real-time authorization gate & hardware fail-safe logic',
    phase: 'Phase 6',
    icon: ShieldCheck,
    color: 'text-rose-400',
  },
  {
    name: 'Database & Audit',
    desc: 'SQLite telemetry log, command history & audit trail',
    phase: 'Phase 7',
    icon: Database,
    color: 'text-purple-400',
  },
];

export const DashboardPlaceholder: React.FC = () => {
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-slate-100 text-left">
          System Initialization Matrix
        </h2>
        <p className="text-sm text-slate-400 text-left mt-1">
          DCRG Core Modules are scaffolded in modular isolation. Implementation unlocks progressively per development roadmap.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {MODULES.map((mod) => {
          const Icon = mod.icon;
          return (
            <div
              key={mod.name}
              className="p-5 bg-slate-900 border border-slate-800 rounded-xl hover:border-slate-700 transition shadow-lg text-left"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="p-2.5 rounded-lg bg-slate-800/80">
                  <Icon className={`w-6 h-6 ${mod.color}`} />
                </div>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono border border-slate-700">
                  {mod.phase}
                </span>
              </div>
              <h3 className="text-base font-semibold text-slate-200 mb-1">{mod.name}</h3>
              <p className="text-xs text-slate-400 leading-relaxed">{mod.desc}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};

