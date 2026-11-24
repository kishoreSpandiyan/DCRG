/**
 * DCRG Frontend API & Subsystem Service Client.
 * Supports Phase 2 Actuator, Phase 3 Voice, and Phase 4 Synchronization Subsystems.
 */

import type {
  SystemStatusPayload,
  JoystickSystemStatus,
  JoystickMode,
  CommonJoystickEvent,
  VoiceSystemStatus,
  VoiceEvent,
  AudioDevice,
  SyncEngineStatus,
  CorrelatedEvent,
  SafetyDecision,
  SafetyEngineStatus,
  ConfirmationAction,
  EmergencySource,
  GatewayExecutionRecord,
  SimulationState,
  CommandExecutionRecord,
  RobotPose,
  SystemOverviewPayload,
  DetailedHealthPayload,
  SystemConfigPayload,
  AuditLogEntry,
  AuditLogQueryFilter,
} from '../types';

export const API_BASE = '/api/v1';

export async function fetchSystemHealth(): Promise<SystemStatusPayload> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) {
      throw new Error(`HTTP error: ${res.status}`);
    }
    return await res.json();
  } catch {
    return {
      status: 'error',
      phase: 'Phase 4 – Event Synchronization & Correlation Engine',
      version: '0.3.0',
      backendConnected: false,
      hardwareDetected: false,
      activeSafetyState: 'DISCONNECTED',
    };
  }
}

// ==========================================
// Phase 2 Joystick Subsystem API
// ==========================================

export async function fetchJoystickStatus(): Promise<JoystickSystemStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/joystick/status`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchDetectedDevices(): Promise<any[]> {
  try {
    const res = await fetch(`${API_BASE}/joystick/devices`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}

export async function rescanJoysticks(): Promise<any> {
  try {
    const res = await fetch(`${API_BASE}/joystick/rescan`, { method: 'POST' });
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return { status: 'error', device_count: 0, devices: [] };
  }
}

export async function setJoystickMode(
  mode: JoystickMode,
  force: boolean = true
): Promise<{ status: string; active_mode: JoystickMode; message: string }> {
  const res = await fetch(`${API_BASE}/joystick/mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, force }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to switch mode' }));
    throw new Error(errData.detail || 'Mode switch rejected');
  }
  return await res.json();
}

export async function postHardwareJoystickInput(
  x: number,
  y: number,
  buttons: boolean[] = [],
  deviceId: string = 'USB-PHYSICAL-CONTROLLER'
): Promise<CommonJoystickEvent> {
  const res = await fetch(`${API_BASE}/joystick/hardware`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      axis_x: x,
      axis_y: y,
      buttons,
      device_id: deviceId,
      client_timestamp: Date.now(),
    }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Hardware input rejected' }));
    throw new Error(errData.detail || 'Hardware input error');
  }
  return await res.json();
}

export async function postVirtualJoystickInput(
  x: number,
  y: number,
  buttons: boolean[] = []
): Promise<CommonJoystickEvent> {
  const res = await fetch(`${API_BASE}/joystick/virtual`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      axis_x: x,
      axis_y: y,
      buttons,
      client_timestamp: Date.now(),
    }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Virtual input rejected' }));
    throw new Error(errData.detail || 'Virtual input error');
  }
  return await res.json();
}

// ==========================================
// Phase 3 Voice & Prosody Subsystem API
// ==========================================

export async function fetchVoiceStatus(): Promise<VoiceSystemStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/voice/status`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchVoiceDevices(): Promise<AudioDevice[]> {
  try {
    const res = await fetch(`${API_BASE}/voice/devices`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}

export async function startVoiceCapture(): Promise<{ status: string; microphone_status: string; message: string }> {
  const res = await fetch(`${API_BASE}/voice/start`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to start microphone' }));
    throw new Error(errData.detail || 'Start capture rejected');
  }
  return await res.json();
}

export async function stopVoiceCapture(): Promise<{ status: string; microphone_status: string; message: string }> {
  const res = await fetch(`${API_BASE}/voice/stop`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to stop microphone' }));
    throw new Error(errData.detail || 'Stop capture rejected');
  }
  return await res.json();
}

export async function setVoiceMute(
  muted: boolean
): Promise<{ status: string; is_muted: boolean; microphone_status: string }> {
  const res = await fetch(`${API_BASE}/voice/mute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ muted }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to update mute state' }));
    throw new Error(errData.detail || 'Mute update failed');
  }
  return await res.json();
}

export async function selectVoiceDevice(
  device_index: number | null
): Promise<{ status: string; selected_device_name?: string; message: string }> {
  const res = await fetch(`${API_BASE}/voice/select-device`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ device_index }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to select device' }));
    throw new Error(errData.detail || 'Select device failed');
  }
  return await res.json();
}

export async function fetchLatestVoiceEvent(): Promise<VoiceEvent | null> {
  try {
    const res = await fetch(`${API_BASE}/voice/latest`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export interface PredefinedSampleItem {
  id: string;
  filename: string;
  command: string;
  label: string;
  description: string;
  url: string;
}

export async function fetchPredefinedSamples(): Promise<PredefinedSampleItem[]> {
  try {
    const res = await fetch(`${API_BASE}/voice/samples`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [
      { id: 'forward', filename: 'forward.wav', command: 'FORWARD', label: 'Move Forward', description: 'Drone move forward', url: '/samples/forward.wav' },
      { id: 'backward', filename: 'backward.wav', command: 'BACKWARD', label: 'Move Backward', description: 'Drone move backward', url: '/samples/backward.wav' },
      { id: 'left', filename: 'left.wav', command: 'LEFT', label: 'Move Left', description: 'Drone move left', url: '/samples/left.wav' },
      { id: 'right', filename: 'right.wav', command: 'RIGHT', label: 'Turn Right', description: 'Drone turn right', url: '/samples/right.wav' },
      { id: 'stop', filename: 'stop.wav', command: 'STOP', label: 'Stop Drone', description: 'Drone stop', url: '/samples/stop.wav' },
      { id: 'emergency_stop', filename: 'emergency_stop.wav', command: 'EMERGENCY_STOP', label: 'Emergency Stop', description: 'Emergency stop', url: '/samples/emergency_stop.wav' },
    ];
  }
}

export async function playPredefinedSample(sampleId: string): Promise<VoiceEvent> {
  const res = await fetch(`${API_BASE}/voice/samples/${encodeURIComponent(sampleId)}/play`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to play sample' }));
    throw new Error(errData.detail || 'Sample execution failed');
  }
  return await res.json();
}

export async function uploadAudioFileBase64(filename: string, base64Data: string): Promise<VoiceEvent> {
  const res = await fetch(`${API_BASE}/voice/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      filename,
      audio_base64: base64Data,
      operator_id: 'OP-UPLOAD',
    }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to upload audio' }));
    throw new Error(errData.detail || 'Audio upload failed');
  }
  return await res.json();
}

// ==========================================
// Phase 4 Event Synchronization API
// ==========================================

export async function fetchSyncStatus(): Promise<SyncEngineStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/sync/status`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchLatestCorrelatedEvent(): Promise<CorrelatedEvent | null> {
  try {
    const res = await fetch(`${API_BASE}/sync/latest`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchCorrelationHistory(limit: number = 20): Promise<CorrelatedEvent[]> {
  try {
    const res = await fetch(`${API_BASE}/sync/history?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}

export async function configureSyncParameters(
  sync_window_ms?: number,
  max_event_age_ms?: number
): Promise<SyncEngineStatus> {
  const res = await fetch(`${API_BASE}/sync/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sync_window_ms, max_event_age_ms }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to configure sync parameters' }));
    throw new Error(errData.detail || 'Sync configuration failed');
  }
  return await res.json();
}


// ==========================================
// Phase 5 Fusion Engine & CRS API
// ==========================================

import type {
  FusionEngineStatus,
  FusionResult,
  FusionConfig,
  ContextState,
} from '../types';

export async function fetchFusionStatus(): Promise<FusionEngineStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/fusion/status`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchLatestFusion(): Promise<FusionResult | null> {
  try {
    const res = await fetch(`${API_BASE}/fusion/latest`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchFusionHistory(limit: number = 20): Promise<FusionResult[]> {
  try {
    const res = await fetch(`${API_BASE}/fusion/history?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchFusionConfig(): Promise<FusionConfig | null> {
  try {
    const res = await fetch(`${API_BASE}/fusion/config`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function updateFusionConfig(config: FusionConfig): Promise<FusionConfig> {
  const res = await fetch(`${API_BASE}/fusion/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to update fusion config' }));
    throw new Error(errData.detail || 'Update configuration failed');
  }
  return await res.json();
}

export async function evaluateManualFusion(payload: {
  voice_command?: string;
  voice_confidence?: number;
  stress_score?: number;
  joystick_direction?: string;
  joystick_intensity?: number;
  axis_x?: number;
  axis_y?: number;
  sync_delta_ms?: number;
}): Promise<FusionResult> {
  const res = await fetch(`${API_BASE}/fusion/evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Evaluation request rejected' }));
    throw new Error(errData.detail || 'Evaluation failed');
  }
  return await res.json();
}

export async function fetchContextState(): Promise<ContextState | null> {
  try {
    const res = await fetch(`${API_BASE}/fusion/context`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function updateContextState(state: ContextState): Promise<ContextState> {
  const res = await fetch(`${API_BASE}/fusion/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(state),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to update context state' }));
    throw new Error(errData.detail || 'Context update failed');
  }
  return await res.json();
}

export async function resetContextState(): Promise<ContextState> {
  const res = await fetch(`${API_BASE}/fusion/context/reset`, {
    method: 'POST',
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Failed to reset context state' }));
    throw new Error(errData.detail || 'Context reset failed');
  }
  return await res.json();
}


// ==========================================
// Phase 6 Tiered Safety Authorization API
// ==========================================

export async function fetchSafetyStatus(): Promise<SafetyEngineStatus | null> {
  try {
    const res = await fetch(`${API_BASE}/safety/status`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchLatestSafetyDecision(): Promise<SafetyDecision | null> {
  try {
    const res = await fetch(`${API_BASE}/safety/latest`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchSafetyHistory(limit: number = 20): Promise<SafetyDecision[]> {
  try {
    const res = await fetch(`${API_BASE}/safety/history?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}

export async function fetchPendingConfirmations(): Promise<SafetyDecision[]> {
  try {
    const res = await fetch(`${API_BASE}/safety/pending`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}

export async function confirmSafetyDecision(
  decision_id: string,
  action: ConfirmationAction,
  operator_id: string = 'OP-PRIMARY',
  reason?: string
): Promise<SafetyDecision> {
  const res = await fetch(`${API_BASE}/safety/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision_id, action, operator_id, reason }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Confirmation request rejected' }));
    throw new Error(errData.detail || 'Confirmation failed');
  }
  return await res.json();
}

export async function triggerEmergencyStop(
  source: EmergencySource = 'SOFTWARE_UI',
  reason: string = 'Operator pressed emergency stop',
  operator_id: string = 'OP-PRIMARY'
): Promise<SafetyDecision> {
  const res = await fetch(`${API_BASE}/safety/estop`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, reason, operator_id }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'E-Stop trigger rejected' }));
    throw new Error(errData.detail || 'E-Stop failed');
  }
  return await res.json();
}

export async function resetEmergencyStop(
  reset_pin: string,
  operator_id: string = 'OP-PRIMARY',
  reason: string = 'Operator safety reset'
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/safety/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reset_pin, operator_id, reason }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Reset authorization denied' }));
    throw new Error(errData.detail || 'Reset failed');
  }
  return await res.json();
}

export async function executeGatewayCommand(
  decision_id: string,
  command: string,
  auth_token?: string | null
): Promise<GatewayExecutionRecord> {
  const res = await fetch(`${API_BASE}/safety/gateway/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision_id, command, auth_token }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({ detail: 'Gateway command rejected' }));
    throw new Error(errData.detail || 'Gateway execution failed');
  }
  return await res.json();
}

export async function fetchGatewayHistory(limit: number = 20): Promise<GatewayExecutionRecord[]> {
  try {
    const res = await fetch(`${API_BASE}/safety/gateway/history?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}


// ==========================================
// Phase 7 Robot Simulation API
// ==========================================

export async function fetchSimulationState(): Promise<SimulationState | null> {
  try {
    const res = await fetch(`${API_BASE}/simulation/state`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchExecutionLogs(limit: number = 50): Promise<CommandExecutionRecord[]> {
  try {
    const res = await fetch(`${API_BASE}/simulation/logs?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}

export async function controlSimulation(
  action: 'START' | 'PAUSE' | 'RESUME' | 'RESET' | 'SET_SPEED' | 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT' | 'STOP',
  speed_multiplier?: number,
  reset_x?: number,
  reset_y?: number
): Promise<SimulationState> {
  const res = await fetch(`${API_BASE}/simulation/control`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, speed_multiplier, reset_x, reset_y }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Control action failed' }));
    throw new Error(err.detail || 'Control failed');
  }
  return await res.json();
}

export async function sendSimCommand(
  cmd: 'FORWARD' | 'BACKWARD' | 'LEFT' | 'RIGHT' | 'STOP'
): Promise<SimulationState> {
  return await controlSimulation(cmd);
}

export async function resetSimulationPose(
  x: number = 0.0,
  y: number = 0.0,
  heading: number = 0.0
): Promise<RobotPose> {
  const res = await fetch(`${API_BASE}/simulation/reset`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ x, y, heading }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Reset pose failed' }));
    throw new Error(err.detail || 'Reset pose failed');
  }
  return await res.json();
}


// ==========================================
// Phase 8 System Integration & Audit API
// ==========================================

export async function fetchSystemOverview(): Promise<SystemOverviewPayload | null> {
  try {
    const res = await fetch(`${API_BASE}/system/overview`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchDetailedHealth(): Promise<DetailedHealthPayload | null> {
  try {
    const res = await fetch(`${API_BASE}/system/health/detailed`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchSystemConfig(): Promise<SystemConfigPayload | null> {
  try {
    const res = await fetch(`${API_BASE}/system/config`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return null;
  }
}

export async function updateSystemConfig(
  parameters: Record<string, any>,
  operator_id: string = 'OP-PRIMARY',
  reason?: string
): Promise<{ status: string; message: string; config: any }> {
  const res = await fetch(`${API_BASE}/system/config`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ parameters, operator_id, reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Config update failed' }));
    throw new Error(err.detail || 'Failed to update system configuration');
  }
  return await res.json();
}

export async function resetSystemConfig(
  operator_id: string = 'OP-PRIMARY'
): Promise<{ status: string; message: string; config: any }> {
  const res = await fetch(`${API_BASE}/system/config/reset?operator_id=${encodeURIComponent(operator_id)}`, {
    method: 'POST',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Config reset failed' }));
    throw new Error(err.detail || 'Failed to reset system configuration');
  }
  return await res.json();
}

export async function fetchSystemLogs(
  filter: AuditLogQueryFilter = {}
): Promise<{ total_records: number; returned_count: number; logs: AuditLogEntry[] }> {
  try {
    const params = new URLSearchParams();
    if (filter.category) params.append('category', filter.category);
    if (filter.safety_state) params.append('safety_state', filter.safety_state);
    if (filter.command) params.append('command', filter.command);
    if (filter.execution_result) params.append('execution_result', filter.execution_result);
    if (filter.limit !== undefined) params.append('limit', String(filter.limit));
    if (filter.offset !== undefined) params.append('offset', String(filter.offset));

    const res = await fetch(`${API_BASE}/system/logs?${params.toString()}`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return { total_records: 0, returned_count: 0, logs: [] };
  }
}

export function getExportLogsUrl(format: 'json' | 'csv' = 'json', filter: AuditLogQueryFilter = {}): string {
  const params = new URLSearchParams({ format });
  if (filter.category) params.append('category', filter.category);
  if (filter.safety_state) params.append('safety_state', filter.safety_state);
  if (filter.command) params.append('command', filter.command);
  if (filter.execution_result) params.append('execution_result', filter.execution_result);
  return `${API_BASE}/system/logs/export?${params.toString()}`;
}

export async function fetchLiveTimeline(limit: number = 30): Promise<AuditLogEntry[]> {
  try {
    const res = await fetch(`${API_BASE}/system/timeline?limit=${limit}`);
    if (!res.ok) throw new Error(`HTTP error: ${res.status}`);
    return await res.json();
  } catch {
    return [];
  }
}
