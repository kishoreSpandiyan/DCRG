/**
 * Real-time WebSocket hook for DCRG Event Synchronization & Correlation (Phase 4).
 * Connects to /ws/sync/stream with auto-reconnection and telemetry caching.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { CorrelatedEvent, SyncEngineStatus } from '../types';
import { fetchSyncStatus, fetchCorrelationHistory, configureSyncParameters } from '../services/api';

export function useSyncStream() {
  const [syncStatus, setSyncStatus] = useState<SyncEngineStatus | null>(null);
  const [latestCorrelation, setLatestCorrelation] = useState<CorrelatedEvent | null>(null);
  const [correlationHistory, setCorrelationHistory] = useState<CorrelatedEvent[]>([]);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const host = window.location.hostname || '127.0.0.1';
    const wsUrl = `ws://${host}:8000/ws/sync/stream`;

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
          if (packet.type === 'INITIAL_STATUS') {
            if (packet.status) setSyncStatus(packet.status);
            if (packet.history && Array.isArray(packet.history)) {
              setCorrelationHistory(packet.history);
              if (packet.history.length > 0) setLatestCorrelation(packet.history[0]);
            }
          } else if (packet.type === 'CORRELATED_EVENT' && packet.data) {
            const ev: CorrelatedEvent = packet.data;
            setLatestCorrelation(ev);
            setCorrelationHistory((prev) => [ev, ...prev.slice(0, 29)]);
          } else if (packet.type === 'CONFIG_UPDATED' && packet.status) {
            setSyncStatus(packet.status);
          } else if (packet.type === 'ERROR') {
            setError(packet.detail || 'Sync WebSocket error');
          }
        } catch (err) {
          console.error('Error parsing Sync WebSocket packet:', err);
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

    // Initial load of history
    fetchCorrelationHistory(20).then((hist) => {
      if (hist && hist.length > 0) {
        setCorrelationHistory(hist);
        setLatestCorrelation(hist[0]);
      }
    });

    const interval = window.setInterval(async () => {
      const st = await fetchSyncStatus();
      if (st) setSyncStatus(st);
    }, 3000);

    return () => {
      window.clearInterval(interval);
      if (reconnectTimeoutRef.current) window.clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const updateSyncWindow = useCallback(async (newWindowMs: number) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'CONFIGURE', sync_window_ms: newWindowMs }));
    }
    const updated = await configureSyncParameters(newWindowMs);
    setSyncStatus(updated);
  }, []);

  return {
    syncStatus,
    latestCorrelation,
    correlationHistory,
    isWsConnected,
    error,
    updateSyncWindow,
  };
}

