/**
 * DCRG Interactive Virtual Joystick Simulator.
 * Provides on-screen touch/mouse drag pad, WASD & Arrow keyboard controls,
 * automatic spring return, virtual button panel, and strict simulation labeling.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { RotateCcw, ShieldAlert, Gamepad2, Keyboard } from 'lucide-react';

interface VirtualJoystickProps {
  onVectorChange: (x: number, y: number, buttons: boolean[]) => void;
  disabled?: boolean;
}

const PAD_RADIUS = 85; // Boundary circle radius in pixels

export const VirtualJoystick: React.FC<VirtualJoystickProps> = ({
  onVectorChange,
  disabled = false,
}) => {
  const [knobPos, setKnobPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [normalized, setNormalized] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [virtualButtons, setVirtualButtons] = useState<boolean[]>([false, false, false, false]);
  const [activeKeys, setActiveKeys] = useState<Set<string>>(new Set());
  const [isDragging, setIsDragging] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);

  // Compute intensity
  const intensity = Math.min(
    1.0,
    Math.sqrt(normalized.x * normalized.x + normalized.y * normalized.y)
  );

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

  // Handle pointer down (mouse or touch)
  const handlePointerDown = (e: React.PointerEvent) => {
    if (disabled) return;
    setIsDragging(true);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    updateKnobFromPointer(e.clientX, e.clientY);
  };

  // Handle pointer move
  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isDragging || disabled) return;
    updateKnobFromPointer(e.clientX, e.clientY);
  };

  // Handle pointer up
  const handlePointerUp = (e: React.PointerEvent) => {
    if (!isDragging) return;
    setIsDragging(false);
    try {
      (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      // Ignore release capture errors on touch cancel
    }
    resetToCenter();
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
      // Guard: Ignore if user is typing into an input field or textarea
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

    // Return to neutral if window blurs (user alt-tabs)
    const handleBlur = () => {
      setActiveKeys(new Set());
      resetToCenter();
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', handleBlur);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', handleBlur);
      resetToCenter();
    };
  }, [disabled, resetToCenter]);

  // Compute direction from activeKeys if not mouse dragging
  useEffect(() => {
    if (isDragging) return;

    if (activeKeys.size === 0) {
      if (normalized.x !== 0 || normalized.y !== 0) {
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
      if (normalized.x !== 0 || normalized.y !== 0) {
        resetToCenter();
      }
      return;
    }

    // Normalize diagonal chords
    const mag = Math.sqrt(kx * kx + ky * ky);
    const normX = Number((kx / mag).toFixed(4));
    const normY = Number((ky / mag).toFixed(4));

    setNormalized({ x: normX, y: normY });
    setKnobPos({
      x: normX * PAD_RADIUS,
      y: -normY * PAD_RADIUS,
    });

    emitVector(normX, normY, virtualButtons);
  }, [activeKeys, isDragging, resetToCenter, emitVector, virtualButtons, normalized.x, normalized.y]);

  // Toggle virtual buttons
  const toggleButton = (idx: number) => {
    const updated = [...virtualButtons];
    updated[idx] = !updated[idx];
    setVirtualButtons(updated);
    emitVector(normalized.x, normalized.y, updated);
  };

  return (
    <div className="flex flex-col items-center bg-slate-900 border border-amber-500/40 rounded-xl p-5 shadow-xl relative overflow-hidden">
      {/* Simulation Indicator Watermark */}
      <div className="absolute top-2 right-2 px-2.5 py-0.5 bg-amber-950/80 border border-amber-600/70 rounded text-[10px] font-mono text-amber-300 font-bold uppercase tracking-wider flex items-center space-x-1">
        <ShieldAlert className="w-3 h-3 text-amber-400" />
        <span>SIMULATION MODE</span>
      </div>

      <div className="flex items-center space-x-2 text-slate-200 self-start mb-3">
        <Gamepad2 className="w-5 h-5 text-amber-400" />
        <h3 className="text-sm font-semibold tracking-wide">Interactive Virtual Joystick</h3>
      </div>

      {/* Canvas / Touch Bounding Circle */}
      <div
        ref={containerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        className={`w-48 h-48 rounded-full border-2 border-slate-700 bg-slate-950 relative flex items-center justify-center cursor-grab active:cursor-grabbing select-none touch-none transition-colors ${
          disabled ? 'opacity-40 pointer-events-none' : 'hover:border-amber-400/50'
        }`}
      >
        {/* Cardinal Grid Crosshairs */}
        <div className="absolute w-full h-[1px] bg-slate-800" />
        <div className="absolute h-full w-[1px] bg-slate-800" />
        <div className="absolute w-24 h-24 rounded-full border border-slate-800/80" />

        {/* Floating Movable Joystick Knob */}
        <div
          style={{
            transform: `translate(${knobPos.x}px, ${knobPos.y}px)`,
            transition: isDragging ? 'none' : 'transform 80ms ease-out',
          }}
          className="w-14 h-14 rounded-full bg-gradient-to-br from-amber-400 to-amber-600 shadow-lg border-2 border-amber-300 flex items-center justify-center text-slate-950 font-bold text-xs"
        >
          {intensity > 0.05 ? `${Math.round(intensity * 100)}%` : '0'}
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
          className="flex items-center space-x-1 px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 rounded text-xs transition"
        >
          <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
          <span>Center</span>
        </button>
      </div>

      {/* Keyboard Controls Reminder */}
      <div className="flex items-center space-x-2 mt-3 text-[11px] text-slate-400 self-start font-mono">
        <Keyboard className="w-3.5 h-3.5 text-slate-500 shrink-0" />
        <span>Keyboard: WASD / Arrow Keys for instant direction</span>
      </div>
    </div>
  );
};
