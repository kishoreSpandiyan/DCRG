/**
 * Real-time WebSocket hook for DCRG Fusion Engine & CRS (Phase 5).
 * Connects to /ws/fusion/stream with auto-reconnection, telemetry caching, and manual evaluation.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type {
  FusionEngineStatus,
  FusionResult,
  FusionConfig,
  ContextState,
} from '../types';
import {
  fetchFusionStatus,
  fetchLatestFusion,
  fetchFusionHistory,
  fetchFusionConfig,
  updateFusionConfig,
  evaluateManualFusion,
  fetchContextState,
  updateContextState,
  resetContextState,
} from '../services/api';

export function useFusionStream() {
  const [fusionStatus, setFusionStatus] = useState<FusionEngineStatus | null>(null);
  const [latestFusion, setLatestFusion] = useState<FusionResult | null>(null);
  const [fusionHistory, setFusionHistory] = useState<FusionResult[]>([]);
  const [fusionConfig, setFusionConfig] = useState<FusionConfig | null>(null);
  const [contextState, setContextState] = useState<ContextState | null>(null);
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

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/fusion/stream`;

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsWsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const packet = JSON.parse(event.data);
          if (packet.type === 'INITIAL_STATE') {
            if (packet.status) setFusionStatus(packet.status);
            if (packet.latest) setLatestFusion(packet.latest);
            if (packet.context) setContextState(packet.context);
          } else if (packet.type === 'FUSION_RESULT' && packet.data) {
            const res: FusionResult = packet.data;
            setLatestFusion(res);
            setFusionHistory((prev) => [res, ...prev.slice(0, 29)]);
          }
        } catch (err) {
          console.error('Error parsing Fusion WebSocket packet:', err);
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
        }, 2500);
      };
    } catch {
      setIsWsConnected(false);
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 2500);
    }
  }, []);

  useEffect(() => {
    connect();

    // Initial load
    fetchFusionStatus().then((st) => st && setFusionStatus(st));
    fetchLatestFusion().then((lat) => lat && setLatestFusion(lat));
    fetchFusionHistory(20).then((hist) => {
      if (hist && hist.length > 0) {
        setFusionHistory(hist);
        if (!latestFusion) setLatestFusion(hist[0]);
      }
    });
    fetchFusionConfig().then((cfg) => cfg && setFusionConfig(cfg));
    fetchContextState().then((ctx) => ctx && setContextState(ctx));

    // Periodic poll for status, latest CRS evaluation & context refresh
    const interval = window.setInterval(async () => {
      const st = await fetchFusionStatus();
      if (st) setFusionStatus(st);
      const lat = await fetchLatestFusion();
      if (lat) setLatestFusion(lat);
      const ctx = await fetchContextState();
      if (ctx) setContextState(ctx);
    }, 2000);

    return () => {
      window.clearInterval(interval);
      if (reconnectTimeoutRef.current) window.clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const handleUpdateConfig = useCallback(async (cfg: FusionConfig) => {
    try {
      const updated = await updateFusionConfig(cfg);
      setFusionConfig(updated);
      const st = await fetchFusionStatus();
      if (st) setFusionStatus(st);
      return true;
    } catch (err: any) {
      setError(err.message || 'Config update failed');
      return false;
    }
  }, []);

  const handleUpdateContext = useCallback(async (ctx: ContextState) => {
    try {
      const updated = await updateContextState(ctx);
      setContextState(updated);
      return true;
    } catch (err: any) {
      setError(err.message || 'Context update failed');
      return false;
    }
  }, []);

  const handleResetContext = useCallback(async () => {
    try {
      const reset = await resetContextState();
      setContextState(reset);
      return true;
    } catch (err: any) {
      setError(err.message || 'Context reset failed');
      return false;
    }
  }, []);

  const handleManualEvaluate = useCallback(
    async (payload: {
      voice_command?: string;
      voice_confidence?: number;
      stress_score?: number;
      joystick_direction?: string;
      joystick_intensity?: number;
      axis_x?: number;
      axis_y?: number;
      sync_delta_ms?: number;
    }) => {
      try {
        const res = await evaluateManualFusion(payload);
        setLatestFusion(res);
        setFusionHistory((prev) => [res, ...prev.slice(0, 29)]);
        return res;
      } catch (err: any) {
        setError(err.message || 'Manual evaluation failed');
        return null;
      }
    },
    []
  );

  return {
    fusionStatus,
    latestFusion,
    fusionHistory,
    fusionConfig,
    contextState,
    isWsConnected,
    error,
    updateConfig: handleUpdateConfig,
    updateContext: handleUpdateContext,
    resetContext: handleResetContext,
    manualEvaluate: handleManualEvaluate,
  };
}

