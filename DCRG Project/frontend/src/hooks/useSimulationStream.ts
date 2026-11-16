/**
 * Real-time WebSocket hook for DCRG Robot Simulation (Phase 7).
 * Connects to /ws/simulation/stream with auto-reconnection,
 * state synchronization, and execution audit logging.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type {
  SimulationState,
  CommandExecutionRecord,
} from '../types';
import {
  fetchSimulationState,
  fetchExecutionLogs,
  controlSimulation,
  resetSimulationPose,
} from '../services/api';

export function useSimulationStream() {
  const [simulationState, setSimulationState] = useState<SimulationState | null>(null);
  const [executionLogs, setExecutionLogs] = useState<CommandExecutionRecord[]>([]);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const host = window.location.hostname || '127.0.0.1';
    const wsUrl = `ws://${host}:8000/ws/simulation/stream`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsWsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'SIMULATION_INIT') {
            if (payload.state) setSimulationState(payload.state);
            if (payload.recent_logs) setExecutionLogs(payload.recent_logs);
          } else if (payload.type === 'SIMULATION_UPDATE') {
            if (payload.state) setSimulationState(payload.state);
          }
        } catch {
          // Ignore parse errors
        }
      };

      ws.onerror = () => {
        setIsWsConnected(false);
      };

      ws.onclose = () => {
        setIsWsConnected(false);
        wsRef.current = null;
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2000);
      };
    } catch (err: any) {
      setIsWsConnected(false);
      setError(err?.message || 'WebSocket connection error');
    }
  }, []);

  const refreshState = useCallback(async () => {
    try {
      const [state, logs] = await Promise.all([
        fetchSimulationState(),
        fetchExecutionLogs(30),
      ]);
      if (state) setSimulationState(state);
      if (logs) setExecutionLogs(logs);
    } catch {
      // Polling fallback silent
    }
  }, []);

  useEffect(() => {
    refreshState();
    connect();

    // Fallback polling for execution logs
    const interval = setInterval(() => {
      fetchExecutionLogs(30).then((logs) => {
        if (logs && logs.length > 0) setExecutionLogs(logs);
      }).catch(() => {});
    }, 1500);

    return () => {
      clearInterval(interval);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, refreshState]);

  const pause = useCallback(async () => {
    try {
      const updated = await controlSimulation('PAUSE');
      setSimulationState(updated);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  const resume = useCallback(async () => {
    try {
      const updated = await controlSimulation('RESUME');
      setSimulationState(updated);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  const resetPose = useCallback(async (x: number = 0.0, y: number = 0.0, heading: number = 0.0) => {
    try {
      await resetSimulationPose(x, y, heading);
      await refreshState();
    } catch (err: any) {
      setError(err.message);
    }
  }, [refreshState]);

  const setSpeedMultiplier = useCallback(async (mult: number) => {
    try {
      const updated = await controlSimulation('SET_SPEED', mult);
      setSimulationState(updated);
    } catch (err: any) {
      setError(err.message);
    }
  }, []);

  return {
    simulationState,
    executionLogs,
    isWsConnected,
    error,
    pause,
    resume,
    resetPose,
    setSpeedMultiplier,
    refreshState,
  };
}

