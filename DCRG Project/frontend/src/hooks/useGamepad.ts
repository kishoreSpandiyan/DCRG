/**
 * Enhanced Gamepad Hook (Browser Gamepad API).
 * Detects and polls USB/Bluetooth/Mobile gamepads (including Xbox Controllers)
 * using requestAnimationFrame to capture high-rate analog axis telemetry.
 */

import { useState, useEffect, useRef } from 'react';

export interface GamepadState {
  connected: boolean;
  id: string | null;
  axisX: number;
  axisY: number;
  intensity: number;
  buttons: boolean[];
}

export function useGamepad(
  onVectorChange?: (x: number, y: number, buttons: boolean[]) => void
): GamepadState {
  const [state, setState] = useState<GamepadState>({
    connected: false,
    id: null,
    axisX: 0,
    axisY: 0,
    intensity: 0,
    buttons: [],
  });

  const animFrameRef = useRef<number | null>(null);
  const lastVectorRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });
  const isRunningRef = useRef(true);

  useEffect(() => {
    isRunningRef.current = true;

    function pollGamepad() {
      if (!isRunningRef.current) return;

      const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
      let activeGp: Gamepad | null = null;

      for (let i = 0; i < gamepads.length; i++) {
        const gp = gamepads[i];
        if (gp && gp.connected) {
          activeGp = gp;
          break;
        }
      }

      if (activeGp) {
        // Standard mapping: axes[0] = Left stick X, axes[1] = Left stick Y (Down is +1, so invert for up = +1)
        const rawX = activeGp.axes.length > 0 ? activeGp.axes[0] : 0;
        const rawY = activeGp.axes.length > 1 ? -activeGp.axes[1] : 0;
        const btns = activeGp.buttons.map((b) => b.pressed);

        const deadzone = 0.08;
        const radius = Math.sqrt(rawX * rawX + rawY * rawY);

        let filteredX = 0;
        let filteredY = 0;
        let intensity = 0;

        if (radius > deadzone) {
          const scaledMag = Math.min(1.0, (radius - deadzone) / (1.0 - deadzone));
          const scale = scaledMag / radius;
          filteredX = Number((rawX * scale).toFixed(4));
          filteredY = Number((rawY * scale).toFixed(4));
          intensity = Number(scaledMag.toFixed(4));
        }

        setState({
          connected: true,
          id: activeGp.id,
          axisX: filteredX,
          axisY: filteredY,
          intensity,
          buttons: btns,
        });

        // Notify callback if vector changed
        if (
          Math.abs(filteredX - lastVectorRef.current.x) > 0.01 ||
          Math.abs(filteredY - lastVectorRef.current.y) > 0.01
        ) {
          lastVectorRef.current = { x: filteredX, y: filteredY };
          if (onVectorChange) {
            onVectorChange(filteredX, filteredY, btns);
          }
        }
      } else {
        if (lastVectorRef.current.x !== 0 || lastVectorRef.current.y !== 0) {
          lastVectorRef.current = { x: 0, y: 0 };
          if (onVectorChange) {
            onVectorChange(0, 0, []);
          }
        }
        setState((prev) => (prev.connected ? {
          connected: false,
          id: null,
          axisX: 0,
          axisY: 0,
          intensity: 0,
          buttons: [],
        } : prev));
      }

      animFrameRef.current = requestAnimationFrame(pollGamepad);
    }

    animFrameRef.current = requestAnimationFrame(pollGamepad);

    return () => {
      isRunningRef.current = false;
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  }, [onVectorChange]);

  return state;
}
