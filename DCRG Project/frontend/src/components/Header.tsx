import React from 'react';
import { ShieldAlert, Cpu, Activity } from 'lucide-react';

interface HeaderProps {
  backendConnected: boolean;
  phase: string;
}

export const Header: React.FC<HeaderProps> = ({ backendConnected, phase }) => {
  return (
    <header className="flex items-center justify-between px-6 py-4 bg-slate-900 border-b border-slate-800 shadow-md">
      <div className="flex items-center space-x-3">
        <ShieldAlert className="w-8 h-8 text-cyan-400" />
        <div>
          <h1 className="text-xl font-bold tracking-wider text-slate-100 m-0 p-0 text-left">
            DCRG <span className="text-cyan-400 font-mono text-xs">v0.1.0</span>
          </h1>
          <p className="text-xs text-slate-400 m-0 p-0 text-left">
            Dynamic Command Reliability Graph • AI + IoT Safety Verification
          </p>
        </div>
      </div>
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2 px-3 py-1 bg-slate-800 rounded-full border border-slate-700 text-xs">
          <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
          <span className="text-slate-300 font-mono">{phase}</span>
        </div>
        <div className="flex items-center space-x-2 px-3 py-1 bg-slate-800 rounded-full border border-slate-700 text-xs">
          <Cpu className={`w-4 h-4 ${backendConnected ? 'text-emerald-400' : 'text-amber-400'}`} />
          <span className="text-slate-300">
            Backend: {backendConnected ? 'Connected' : 'Offline / Standalone'}
          </span>
        </div>
      </div>
    </header>
  );
};

