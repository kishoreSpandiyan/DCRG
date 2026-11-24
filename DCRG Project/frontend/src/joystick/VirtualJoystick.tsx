/**
 * DCRG Interactive Virtual Joystick Simulator.
 * Provides on-screen touch/mouse drag pad with robust pointer capture,
 * Directional D-Pad quick buttons, Hold Position (Sticky) mode for contradiction testing,
 * WASD & Arrow keyboard controls, 10Hz throttled telemetry loop, and strict simulation labeling.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  RotateCcw,
  ShieldAlert,
  Gamepad2,
  Keyboard,
  Lock,
  Unlock,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  CircleDot,
} from 'lucide-react';

interface VirtualJoystickProps {
  onVectorChange: (x: number, y: number, buttons: boolean[]) => void;
  disabled?: boolean;
  /** When hardware axes arrive, mirror knob position without re-emitting */
  externalAxes?: { x: number; y: number } | null;
}

const PAD_RADIUS = 85; // Boundary circle radius in pixels
const DEFLECTION_MAGNITUDE = 0.85; // Standard deflection for D-pad buttons

export const VirtualJoystick: React.FC<VirtualJoystickProps> = ({
  onVectorChange,
  disabled = false,
  externalAxes = null,
}) => {
  const [knobPos, setKnobPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [normalized, setNormalized] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [virtualButtons, setVirtualButtons] = useState<boolean[]>([false, false, false, false]);
  const [activeKeys, setActiveKeys] = useState<Set<string>>(new Set());
  const [isDragging, setIsDragging] = useState(false);
  // Default sticky mode to true so operators can release mouse and interact with voice controls
  const [isSticky, setIsSticky] = useState(true);

  const containerRef = useRef<HTMLDivElement>(null);

  // Track whether the knob is currently being driven by external (hardware) axes
  const [isExternalDriven, setIsExternalDriven] = useState(false);
  const externalTimeoutRef = useRef<number | null>(null);

  // Mirror hardware joystick axes onto the knob (read-only, no re-emit)
  useEffect(() => {
    if (!externalAxes || isDragging || activeKeys.size > 0) {
      return;
    }
    const ex = externalAxes.x;
    const ey = externalAxes.y;

    // Near-zero noise gate
    if (Math.abs(ex) < 0.02 && Math.abs(ey) < 0.02) {
      setKnobPos({ x: 0, y: 0 });
      setNormalized({ x: 0, y: 0 });
      setIsExternalDriven(false);
      return;
    }

    setKnobPos({ x: ex * PAD_RADIUS, y: -ey * PAD_RADIUS });
    setNormalized({ x: ex, y: ey });
    setIsExternalDriven(true);

    // Auto-clear flag after 500ms of no new external updates
    if (externalTimeoutRef.current) window.clearTimeout(externalTimeoutRef.current);
    externalTimeoutRef.current = window.setTimeout(() => {
      setIsExternalDriven(false);
    }, 500);
    // Note: DO NOT call emitVector here — hardware already sent to backend via WebSocket.
    // Re-emitting would cause a feedback loop.
  }, [externalAxes, isDragging, activeKeys]);

  // Compute intensity
  const intensity = Math.min(
    1.0,
    Math.sqrt(normalized.x * normalized.x + normalized.y * normalized.y)
  );

  // Determine cardinal direction label
  const getDirectionLabel = (nx: number, ny: number): string => {
    if (Math.abs(nx) < 0.15 && Math.abs(ny) < 0.15) return 'CENTER';
    if (Math.abs(nx) > Math.abs(ny) * 1.5) {
      return nx > 0 ? 'RIGHT' : 'LEFT';
    }
    if (Math.abs(ny) > Math.abs(nx) * 1.5) {
      return ny > 0 ? 'FORWARD' : 'BACKWARD';
    }
    if (ny > 0) {
      return nx > 0 ? 'FORWARD_RIGHT' : 'FORWARD_LEFT';
    }
    return nx > 0 ? 'BACKWARD_RIGHT' : 'BACKWARD_LEFT';
  };

  const directionLabel = getDirectionLabel(normalized.x, normalized.y);

  // Emit vector change to parent / WebSocket
  const emitVector = useCallback(
    (nx: number, ny: number, btns: boolean[]) => {
      onVectorChange(nx, ny, btns);
    },
    [onVectorChange]
  );

  // Safely reset knob to center
  const resetToCenter = useCallback(() => {
    setKnobPos({ x: 0, y: 0 });
    setNormalized({ x: 0, y: 0 });
    emitVector(0.0, 0.0, virtualButtons);
  }, [emitVector, virtualButtons]);

  // Set direction via D-Pad quick deflect
  const setDirection = useCallback(
    (nx: number, ny: number) => {
      if (disabled) return;
      const targetX = Number(nx.toFixed(4));
      const targetY = Number(ny.toFixed(4));
      const px = targetX * PAD_RADIUS;
      const py = -targetY * PAD_RADIUS; // Screen Y inverted

      setKnobPos({ x: px, y: py });
      setNormalized({ x: targetX, y: targetY });
      emitVector(targetX, targetY, virtualButtons);
    },
    [disabled, emitVector, virtualButtons]
  );

  // Handle pointer down on the pad container
  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (disabled) return;
    setIsDragging(true);
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      // Ignored if capture unsupported
    }
    updateKnobFromPointer(e.clientX, e.clientY);
  };

  // Handle pointer move
  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging || disabled) return;
    updateKnobFromPointer(e.clientX, e.clientY);
  };

  // Handle pointer up
  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!isDragging) return;
    setIsDragging(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      // Ignored
    }

    if (!isSticky) {
      resetToCenter();
    } else {
      // Keep current deflection in sticky mode and re-emit
      emitVector(normalized.x, normalized.y, virtualButtons);
    }
  };

  const updateKnobFromPointer = (clientX: number, clientY: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;

    let dx = clientX - centerX;
    let dy = clientY - centerY;

    // Convert screen coordinates to Cartesian (Screen Y is inverted: Up is -ScreenY, so Cart Y = -dy)
    const distance = Math.sqrt(dx * dx + dy * dy);

    if (distance > PAD_RADIUS) {
      const angle = Math.atan2(dy, dx);
      dx = Math.cos(angle) * PAD_RADIUS;
      dy = Math.sin(angle) * PAD_RADIUS;
    }

    setKnobPos({ x: dx, y: dy });

    const normX = Number((dx / PAD_RADIUS).toFixed(4));
    const normY = Number((-dy / PAD_RADIUS).toFixed(4)); // Invert Y so up is +1.0

    setNormalized({ x: normX, y: normY });
    emitVector(normX, normY, virtualButtons);
  };

  // Keyboard controls listener (WASD and Arrow keys)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (disabled) return;
      const target = e.target as HTMLElement;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }

      const key = e.key.toLowerCase();
      if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(key)) {
        e.preventDefault();
        setActiveKeys((prev) => {
          const updated = new Set(prev);
          updated.add(key);
          return updated;
        });
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      const key = e.key.toLowerCase();
      if (['w', 'a', 's', 'd', 'arrowup', 'arrowdown', 'arrowleft', 'arrowright'].includes(key)) {
        setActiveKeys((prev) => {
          const updated = new Set(prev);
          updated.delete(key);
          return updated;
        });
      }
    };

    const handleBlur = () => {
      setActiveKeys(new Set());
      if (!isSticky) resetToCenter();
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
    };
  }, [disabled, isSticky, resetToCenter]);

  // Compute direction from activeKeys if not mouse dragging
  useEffect(() => {
    if (isDragging) return;

    if (activeKeys.size === 0) {
      if (!isSticky && (normalized.x !== 0 || normalized.y !== 0)) {
        resetToCenter();
      }
      return;
    }

    let kx = 0;
    let ky = 0;

    if (activeKeys.has('w') || activeKeys.has('arrowup')) ky += 1;
    if (activeKeys.has('s') || activeKeys.has('arrowdown')) ky -= 1;
    if (activeKeys.has('a') || activeKeys.has('arrowleft')) kx -= 1;
    if (activeKeys.has('d') || activeKeys.has('arrowright')) kx += 1;

    if (kx === 0 && ky === 0) {
      if (!isSticky && (normalized.x !== 0 || normalized.y !== 0)) {
        resetToCenter();
      }
      return;
    }

    const mag = Math.sqrt(kx * kx + ky * ky);
    const normX = Number((kx / mag).toFixed(4));
    const normY = Number((ky / mag).toFixed(4));

    setNormalized({ x: normX, y: normY });
    setKnobPos({
      x: normX * PAD_RADIUS,
      y: -normY * PAD_RADIUS,
    });

    emitVector(normX, normY, virtualButtons);
  }, [activeKeys, isDragging, isSticky, resetToCenter, emitVector, virtualButtons, normalized.x, normalized.y]);

  // Continuous 10Hz telemetry streaming loop when deflected (100ms interval avoids WebSocket flooding)
  useEffect(() => {
    const isDeflected = normalized.x !== 0 || normalized.y !== 0;
    if (!isDeflected || disabled) return;

    const interval = window.setInterval(() => {
      emitVector(normalized.x, normalized.y, virtualButtons);
    }, 100); // 10 Hz = 100ms

    return () => window.clearInterval(interval);
  }, [normalized.x, normalized.y, virtualButtons, emitVector, disabled]);

  // Toggle virtual buttons
  const toggleButton = (idx: number) => {
    const updated = [...virtualButtons];
    updated[idx] = !updated[idx];
    setVirtualButtons(updated);
    emitVector(normalized.x, normalized.y, updated);
  };

  return (
    <div className="flex flex-col items-center bg-slate-900 border border-amber-500/40 rounded-xl p-5 shadow-xl relative overflow-hidden select-none">
      {/* Simulation / Hardware Indicator Watermark */}
      <div className={`absolute top-2 right-2 px-2.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-wider flex items-center space-x-1 ${
        isExternalDriven
          ? 'bg-emerald-950/80 border border-emerald-600/70 text-emerald-300'
          : 'bg-amber-950/80 border border-amber-600/70 text-amber-300'
      }`}>
        <ShieldAlert className={`w-3 h-3 ${isExternalDriven ? 'text-emerald-400' : 'text-amber-400'}`} />
        <span>{isExternalDriven ? 'HARDWARE MODE' : 'SIMULATION MODE'}</span>
      </div>

      <div className="flex items-center justify-between w-full mb-3">
        <div className="flex items-center space-x-2 text-slate-200">
          <Gamepad2 className="w-5 h-5 text-amber-400" />
          <h3 className="text-sm font-semibold tracking-wide">Interactive Virtual Joystick</h3>
        </div>

        {/* Hold Position / Auto-Spring Toggle */}
        <button
          type="button"
          onClick={() => setIsSticky(!isSticky)}
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs font-mono font-bold transition border ${
            isSticky
              ? 'bg-amber-950/80 text-amber-300 border-amber-500/80 shadow-sm'
              : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-slate-200'
          }`}
          title={
            isSticky
              ? 'Hold Position is ON: Releasing mouse keeps joystick deflected so you can test speech contradiction.'
              : 'Auto-Center is ON: Releasing mouse returns joystick knob to (0,0).'
          }
        >
          {isSticky ? (
            <>
              <Lock className="w-3.5 h-3.5 text-amber-400" />
              <span>HOLD POSITION (ON)</span>
            </>
          ) : (
            <>
              <Unlock className="w-3.5 h-3.5 text-slate-400" />
              <span>AUTO-CENTER (SPRING)</span>
            </>
          )}
        </button>
      </div>

      {/* Main Touch / Mouse Pad Circle */}
      <div
        ref={containerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        className={`w-48 h-48 rounded-full border-2 border-slate-700 bg-slate-950 relative flex items-center justify-center cursor-grab active:cursor-grabbing touch-none transition-colors ${
          disabled ? 'opacity-40 pointer-events-none' : 'hover:border-amber-400/50'
        }`}
      >
        {/* Cardinal Grid Crosshairs */}
        <div className="absolute w-full h-[1px] bg-slate-800" />
        <div className="absolute h-full w-[1px] bg-slate-800" />
        <div className="absolute w-24 h-24 rounded-full border border-slate-800/80" />

        {/* Direction Indicator Overlay */}
        <div className="absolute top-2 text-[10px] font-mono text-slate-600 font-bold tracking-widest">
          FWD
        </div>
        <div className="absolute bottom-2 text-[10px] font-mono text-slate-600 font-bold tracking-widest">
          BWD
        </div>
        <div className="absolute left-2 text-[10px] font-mono text-slate-600 font-bold tracking-widest">
          LEFT
        </div>
        <div className="absolute right-2 text-[10px] font-mono text-slate-600 font-bold tracking-widest">
          RIGHT
        </div>

        {/* Floating Movable Joystick Knob */}
        <div
          style={{
            transform: `translate(${knobPos.x}px, ${knobPos.y}px)`,
            transition: isDragging ? 'none' : 'transform 100ms ease-out',
          }}
          className={`w-14 h-14 rounded-full shadow-lg border-2 flex items-center justify-center text-slate-950 font-bold text-xs select-none pointer-events-none ${
            intensity > 0.1
              ? 'bg-gradient-to-br from-amber-400 to-amber-600 border-amber-300 shadow-amber-500/20'
              : 'bg-gradient-to-br from-slate-600 to-slate-700 border-slate-500 text-slate-200'
          }`}
        >
          {intensity > 0.05 ? `${Math.round(intensity * 100)}%` : '0'}
        </div>
      </div>

      {/* Directional D-Pad Quick Deflection Buttons (Prevents Mouse Slipping & Guarantees Instant Testing) */}
      <div className="mt-4 flex flex-col items-center space-y-1 w-full">
        <div className="text-[11px] font-mono text-slate-400 flex items-center space-x-1.5">
          <span>DIRECTION QUICK D-PAD:</span>
          <span className="text-amber-400 font-bold">{directionLabel}</span>
        </div>

        {/* D-Pad Layout */}
        <div className="flex flex-col items-center space-y-1 pt-1">
          {/* Row 1: Forward */}
          <button
            type="button"
            onClick={() => setDirection(0.0, DEFLECTION_MAGNITUDE)}
            className={`px-3 py-1.5 rounded flex items-center space-x-1 text-xs font-mono font-bold transition border ${
              directionLabel === 'FORWARD'
                ? 'bg-amber-500 text-slate-950 border-amber-300'
                : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750 hover:border-amber-400/50'
            }`}
          >
            <ArrowUp className="w-3.5 h-3.5" />
            <span>FORWARD (+0.85)</span>
          </button>

          {/* Row 2: Left, Center, Right */}
          <div className="flex items-center space-x-1">
            <button
              type="button"
              onClick={() => setDirection(-DEFLECTION_MAGNITUDE, 0.0)}
              className={`px-3 py-1.5 rounded flex items-center space-x-1 text-xs font-mono font-bold transition border ${
                directionLabel === 'LEFT'
                  ? 'bg-amber-500 text-slate-950 border-amber-300'
                  : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750 hover:border-amber-400/50'
              }`}
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>LEFT</span>
            </button>

            <button
              type="button"
              onClick={resetToCenter}
              className={`px-3 py-1.5 rounded flex items-center space-x-1 text-xs font-mono font-bold transition border ${
                directionLabel === 'CENTER'
                  ? 'bg-slate-700 text-white border-slate-500'
                  : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-750'
              }`}
              title="Reset Joystick to Center (0.0, 0.0)"
            >
              <CircleDot className="w-3.5 h-3.5 text-slate-400" />
              <span>CENTER</span>
            </button>

            <button
              type="button"
              onClick={() => setDirection(DEFLECTION_MAGNITUDE, 0.0)}
              className={`px-3 py-1.5 rounded flex items-center space-x-1 text-xs font-mono font-bold transition border ${
                directionLabel === 'RIGHT'
                  ? 'bg-amber-500 text-slate-950 border-amber-300'
                  : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750 hover:border-amber-400/50'
              }`}
            >
              <span>RIGHT</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Row 3: Backward */}
          <button
            type="button"
            onClick={() => setDirection(0.0, -DEFLECTION_MAGNITUDE)}
            className={`px-3 py-1.5 rounded flex items-center space-x-1 text-xs font-mono font-bold transition border ${
              directionLabel === 'BACKWARD'
                ? 'bg-amber-500 text-slate-950 border-amber-300'
                : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750 hover:border-amber-400/50'
            }`}
          >
            <ArrowDown className="w-3.5 h-3.5" />
            <span>BACKWARD (-0.85)</span>
          </button>
        </div>
      </div>

      {/* Axis & Intensity Readout */}
      <div className="grid grid-cols-3 gap-2 w-full mt-4 text-center font-mono text-xs">
        <div className="bg-slate-950 p-2 rounded border border-slate-800">
          <span className="text-slate-500 block text-[10px]">AXIS X</span>
          <span className={normalized.x !== 0 ? 'text-amber-400 font-bold' : 'text-slate-400'}>
            {normalized.x >= 0 ? `+${normalized.x.toFixed(2)}` : normalized.x.toFixed(2)}
          </span>
        </div>
        <div className="bg-slate-950 p-2 rounded border border-slate-800">
          <span className="text-slate-500 block text-[10px]">AXIS Y</span>
          <span className={normalized.y !== 0 ? 'text-amber-400 font-bold' : 'text-slate-400'}>
            {normalized.y >= 0 ? `+${normalized.y.toFixed(2)}` : normalized.y.toFixed(2)}
          </span>
        </div>
        <div className="bg-slate-950 p-2 rounded border border-slate-800">
          <span className="text-slate-500 block text-[10px]">INTENSITY</span>
          <span className={intensity > 0.1 ? 'text-emerald-400 font-bold' : 'text-slate-400'}>
            {(intensity * 100).toFixed(1)}%
          </span>
        </div>
      </div>

      {/* Virtual Buttons & Reset */}
      <div className="flex items-center justify-between w-full mt-4">
        <div className="flex space-x-1.5">
          {virtualButtons.map((pressed, i) => (
            <button
              key={i}
              type="button"
              onClick={() => toggleButton(i)}
              className={`px-2.5 py-1 text-xs font-mono font-bold rounded border transition ${
                pressed
                  ? 'bg-amber-500 text-slate-950 border-amber-400'
                  : 'bg-slate-800 text-slate-300 border-slate-700 hover:border-slate-600'
              }`}
            >
              B{i + 1}
            </button>
          ))}
        </div>

        <button
          type="button"
          onClick={resetToCenter}
          className="flex items-center space-x-1 px-3 py-1 bg-slate-800 hover:bg-slate-750 text-slate-200 border border-slate-700 rounded text-xs transition"
        >
          <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
          <span>Reset Center</span>
        </button>
      </div>

      {/* Keyboard Controls Reminder */}
      <div className="flex items-center space-x-2 mt-3 text-[11px] text-slate-400 self-start font-mono">
        <Keyboard className="w-3.5 h-3.5 text-slate-500 shrink-0" />
        <span>Keyboard: WASD / Arrow Keys supported</span>
      </div>
    </div>
  );
};
