/**
 * Real-time WebSocket hook for DCRG Voice Recognition and Prosody Subsystem.
 * Connects to /ws/voice/stream with automatic reconnection and fallback polling.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { VoiceEvent, VoiceSystemStatus, MicrophoneStatus } from '../types';
import { fetchVoiceStatus } from '../services/api';

export function useVoiceStream() {
  const [voiceStatus, setVoiceStatus] = useState<VoiceSystemStatus | null>(null);
  const [lastEvent, setLastEvent] = useState<VoiceEvent | null>(null);
  const [eventHistory, setEventHistory] = useState<VoiceEvent[]>([]);
  const [isWsConnected, setIsWsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const host = window.location.hostname || '127.0.0.1';
    const wsUrl = `ws://${host}:8000/ws/voice/stream`;

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
          if (packet.type === 'INITIAL_STATUS' && packet.status) {
            setVoiceStatus(packet.status);
            if (packet.status.last_event) {
              setLastEvent(packet.status.last_event);
            }
          } else if (packet.type === 'VOICE_EVENT' && packet.data) {
            const vEvent: VoiceEvent = packet.data;
            setLastEvent(vEvent);
            setEventHistory((prev) => [vEvent, ...prev.slice(0, 19)]);
          } else if (packet.type === 'MIC_CONTROL_RESULT' && packet.status) {
            setVoiceStatus(packet.status);
          } else if (packet.type === 'ERROR') {
            setError(packet.detail || 'WebSocket error');
          }
        } catch (err) {
          console.error('Error parsing Voice WebSocket packet:', err);
        }
      };

      ws.onerror = () => {
        setIsWsConnected(false);
      };

      ws.onclose = () => {
        setIsWsConnected(false);
        wsRef.current = null;
        // Schedule auto-reconnect
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 2500);
      };
    } catch (e) {
      setIsWsConnected(false);
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, 2500);
    }
  }, []);

  useEffect(() => {
    connect();

    // Fallback status polling every 3 seconds
    const interval = window.setInterval(async () => {
      const st = await fetchVoiceStatus();
      if (st) {
        setVoiceStatus(st);
        if (st.last_event && !lastEvent) {
          setLastEvent(st.last_event);
        }
      }
    }, 3000);

    return () => {
      window.clearInterval(interval);
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const startMic = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'START_MIC' }));
    }
  }, []);

  const stopMic = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'STOP_MIC' }));
    }
  }, []);

  const toggleMute = useCallback((muted: boolean) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'SET_MUTE', muted }));
    }
  }, []);

  return {
    voiceStatus,
    lastEvent,
    eventHistory,
    isWsConnected,
    error,
    startMic,
    stopMic,
    toggleMute,
    micStatus: (voiceStatus?.microphone_status || 'DISCONNECTED') as MicrophoneStatus,
  };
}

