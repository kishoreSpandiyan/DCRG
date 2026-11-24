/**
 * Real-time WebSocket hook for DCRG Tiered Safety Authorization (Phase 6).
 * Connects to /ws/safety/stream with auto-reconnection, E-Stop latch sync,
 * and live human confirmation dispatching.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type {
  SafetyEngineStatus,
  SafetyDecision,
  GatewayExecutionRecord,
  ConfirmationAction,
  EmergencySource,
} from '../types';
import {
  fetchSafetyStatus,
  fetchLatestSafetyDecision,
  fetchSafetyHistory,
  fetchPendingConfirmations,
  confirmSafetyDecision,
  triggerEmergencyStop,
  resetEmergencyStop,
  executeGatewayCommand,
  fetchGatewayHistory,
} from '../services/api';

export function useSafetyStream() {
  const [safetyStatus, setSafetyStatus] = useState<SafetyEngineStatus | null>(null);
  const [latestDecision, setLatestDecision] = useState<SafetyDecision | null>(null);
  const [safetyHistory, setSafetyHistory] = useState<SafetyDecision[]>([]);
  const [pendingConfirmations, setPendingConfirmations] = useState<SafetyDecision[]>([]);
  const [gatewayHistory, setGatewayHistory] = useState<GatewayExecutionRecord[]>([]);
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
    const wsUrl = `${protocol}//${window.location.host}/ws/safety/stream`;

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
          if (packet.type === 'INITIAL_SAFETY_STATE') {
            if (packet.status) setSafetyStatus(packet.status);
            if (packet.latest) setLatestDecision(packet.latest);
            if (packet.pending && Array.isArray(packet.pending)) setPendingConfirmations(packet.pending);
            if (packet.gateway_history && Array.isArray(packet.gateway_history)) setGatewayHistory(packet.gateway_history);
          } else if (packet.type === 'SAFETY_DECISION' && packet.data) {
            const dec: SafetyDecision = packet.data;
            setLatestDecision(dec);
            setSafetyHistory((prev) => [dec, ...prev.slice(0, 29)]);
            if (packet.status) setSafetyStatus(packet.status);

            // Update pending list if YELLOW
            if (dec.authorization_decision === 'HOLD_PENDING_CONFIRMATION') {
              setPendingConfirmations((prev) => {
                const filtered = prev.filter((p) => p.decision_id !== dec.decision_id);
                return [dec, ...filtered];
              });
            } else {
              // Remove if resolved
              setPendingConfirmations((prev) => prev.filter((p) => p.decision_id !== dec.decision_id));
            }
          }
        } catch (err) {
          console.error('Error parsing Safety WebSocket packet:', err);
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
    fetchSafetyStatus().then((st) => st && setSafetyStatus(st));
    fetchLatestSafetyDecision().then((lat) => lat && setLatestDecision(lat));
    fetchPendingConfirmations().then((pend) => pend && setPendingConfirmations(pend));
    fetchSafetyHistory(20).then((hist) => {
      if (hist && hist.length > 0) {
        setSafetyHistory(hist);
        if (!latestDecision) setLatestDecision(hist[0]);
      }
    });
    fetchGatewayHistory(10).then((gw) => gw && setGatewayHistory(gw));

    // Periodic poll for sync
    const interval = window.setInterval(async () => {
      const st = await fetchSafetyStatus();
      if (st) setSafetyStatus(st);
      const pend = await fetchPendingConfirmations();
      if (pend) setPendingConfirmations(pend);
      const gw = await fetchGatewayHistory(10);
      if (gw) setGatewayHistory(gw);
    }, 2000);

    return () => {
      window.clearInterval(interval);
      if (reconnectTimeoutRef.current) window.clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const handleConfirmDecision = useCallback(
    async (decisionId: string, action: ConfirmationAction, operatorId: string = 'OP-PRIMARY', reason?: string) => {
      try {
        const updated = await confirmSafetyDecision(decisionId, action, operatorId, reason);
        setPendingConfirmations((prev) => prev.filter((p) => p.decision_id !== decisionId));
        setLatestDecision(updated);
        setSafetyHistory((prev) => [updated, ...prev.slice(0, 29)]);
        return updated;
      } catch (err: any) {
        setError(err.message || 'Confirmation failed');
        return null;
      }
    },
    []
  );

  const handleTriggerEStop = useCallback(
    async (source: EmergencySource = 'SOFTWARE_UI', reason: string = 'Operator pressed emergency stop') => {
      try {
        const estopDec = await triggerEmergencyStop(source, reason);
        setLatestDecision(estopDec);
        setPendingConfirmations([]);
        const st = await fetchSafetyStatus();
        if (st) setSafetyStatus(st);
        return estopDec;
      } catch (err: any) {
        setError(err.message || 'E-Stop trigger failed');
        return null;
      }
    },
    []
  );

  const handleResetEStop = useCallback(async (resetPin: string, operatorId: string = 'OP-PRIMARY') => {
    try {
      const res = await resetEmergencyStop(resetPin, operatorId);
      const st = await fetchSafetyStatus();
      if (st) setSafetyStatus(st);
      return res;
    } catch (err: any) {
      setError(err.message || 'Reset authorization denied');
      return null;
    }
  }, []);

  const handleDispatchGateway = useCallback(async (decisionId: string, command: string, authToken?: string | null) => {
    try {
      const rec = await executeGatewayCommand(decisionId, command, authToken);
      setGatewayHistory((prev) => [rec, ...prev.slice(0, 19)]);
      return rec;
    } catch (err: any) {
      setError(err.message || 'Gateway dispatch failed');
      return null;
    }
  }, []);

  return {
    safetyStatus,
    latestDecision,
    safetyHistory,
    pendingConfirmations,
    gatewayHistory,
    isWsConnected,
    error,
    confirmDecision: handleConfirmDecision,
    triggerEStop: handleTriggerEStop,
    resetEStop: handleResetEStop,
    dispatchGateway: handleDispatchGateway,
  };
}

