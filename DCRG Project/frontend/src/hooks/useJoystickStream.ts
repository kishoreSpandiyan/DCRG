/**
 * React WebSocket Hook for Joystick Input Streaming.
 * Handles duplex communication with /ws/joystick/stream.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import type { CommonJoystickEvent, JoystickSystemStatus, JoystickMode } from '../types';

export interface UseJoystickStreamReturn {
  isConnected: boolean;
  status: JoystickSystemStatus | null;
  lastEvent: CommonJoystickEvent | null;
  eventHistory: CommonJoystickEvent[];
  sendVirtualInput: (x: number, y: number, buttons?: boolean[]) => void;
  sendHardwareInput: (x: number, y: number, buttons?: boolean[], deviceId?: string) => void;
  requestModeChange: (mode: JoystickMode, force?: boolean) => void;
  error: string | null;
}

export function useJoystickStream(): UseJoystickStreamReturn {
  const [isConnected, setIsConnected] = useState(false);
  const [status, setStatus] = useState<JoystickSystemStatus | null>(null);
  const [lastEvent, setLastEvent] = useState<CommonJoystickEvent | null>(null);
  const [eventHistory, setEventHistory] = useState<CommonJoystickEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/joystick/stream`;

    try {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'JOYSTICK_EVENT' && payload.data) {
            const joyEvent: CommonJoystickEvent = payload.data;
            setLastEvent(joyEvent);
            setEventHistory((prev) => [joyEvent, ...prev.slice(0, 24)]);
          } else if (payload.type === 'INITIAL_STATUS' && payload.status) {
            setStatus(payload.status);
          } else if (payload.type === 'MODE_CHANGE_RESULT') {
            if (payload.success) {
              setStatus((prev) => prev ? { ...prev, active_mode: payload.active_mode } : null);
              setError(null);
            } else {
              setError(payload.message || 'Mode change rejected');
            }
          } else if (payload.type === 'ERROR') {
            setError(payload.detail || 'WebSocket error');
          }
        } catch {
          // Ignore malformed debug frames
        }
      };

      ws.onerror = () => {
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connectRef.current();
        }, 2000);
      };
    } catch (err) {
      setError(String(err));
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connectRef.current();
      }, 3000);
    }
  }, []);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connect]);

  const sendVirtualInput = useCallback((x: number, y: number, buttons: boolean[] = []) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        JSON.stringify({
          type: 'VIRTUAL_INPUT',
          axis_x: x,
          axis_y: y,
          buttons,
          client_timestamp: Date.now(),
        })
      );
    }
  }, []);

  const sendHardwareInput = useCallback(
    (x: number, y: number, buttons: boolean[] = [], deviceId: string = 'USB-PHYSICAL-CONTROLLER') => {
      if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
        socketRef.current.send(
          JSON.stringify({
            type: 'HARDWARE_INPUT',
            axis_x: x,
            axis_y: y,
            buttons,
            device_id: deviceId,
            client_timestamp: Date.now(),
          })
        );
      }
    },
    []
  );

  const requestModeChange = useCallback((mode: JoystickMode, force: boolean = true) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(
        JSON.stringify({
          type: 'SET_MODE',
          mode,
          force,
        })
      );
    }
  }, []);

  return {
    isConnected,
    status,
    lastEvent,
    eventHistory,
    sendVirtualInput,
    sendHardwareInput,
    requestModeChange,
    error,
  };
}
