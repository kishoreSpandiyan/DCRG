import React from 'react';
import { Bot } from 'lucide-react';

export const SimulationPlaceholder: React.FC = () => {
  return (
    <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl text-left">
      <div className="flex items-center space-x-2 text-slate-300 mb-2">
        <Bot className="w-5 h-5 text-cyan-400" />
        <h3 className="font-semibold text-sm">Simulation Subsystem (Phase 9)</h3>
      </div>
      <p className="text-xs text-slate-400">
        Simulated 2D/3D robot kinematics, virtual obstacles, and sensor events will be rendered in Phase 9. All simulation data is strictly isolated from physical actuator streams.
      </p>
    </div>
  );
};

