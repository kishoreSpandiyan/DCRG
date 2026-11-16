/**
 * Dynamic Command Reliability Graph (DCRG)
 * Core TypeScript Interfaces (Phase 2, Phase 3, & Phase 4)
 */

export type SafetyState = 'NORMAL' | 'DEGRADED' | 'EMERGENCY_STOP' | 'DISCONNECTED';

export type JoystickDirection =
  | 'FORWARD'
  | 'BACKWARD'
  | 'LEFT'
  | 'RIGHT'
  | 'CENTER'
  | 'FORWARD_LEFT'
  | 'FORWARD_RIGHT'
  | 'BACKWARD_LEFT'
  | 'BACKWARD_RIGHT'
  | 'UNKNOWN';

export type JoystickSource = 'PHYSICAL_HARDWARE' | 'VIRTUAL_SIMULATION';
export type ConnectionStatus = 'CONNECTED' | 'DISCONNECTED' | 'DEGRADED';
export type CalibrationStatus = 'CALIBRATED' | 'UNCALIBRATED' | 'DEFAULT';
export type DataValidity = 'VALID' | 'STALE' | 'CORRUPTED';
export type JoystickMode = 'VIRTUAL_SIMULATION' | 'REAL_HARDWARE';

export interface CommonJoystickEvent {
  event_id: string;
  source: JoystickSource;
  device_id: string;
  timestamp: number;
  axis_x: number; // -1.0 to 1.0
  axis_y: number; // -1.0 to 1.0
  direction: JoystickDirection;
  intensity: number; // 0.0 to 1.0
  buttons: boolean[];
  connection_status: ConnectionStatus;
  calibration_status: CalibrationStatus;
  data_validity: DataValidity;
  is_simulation: boolean;
}

export interface JoystickSystemStatus {
  active_mode: JoystickMode;
  physical_hardware_detected: boolean;
  connected_device_count: number;
  primary_device_name?: string | null;
  primary_device_id?: string | null;
  connection_status: ConnectionStatus;
  calibration_status: CalibrationStatus;
  last_event?: CommonJoystickEvent | null;
  error_message?: string | null;
}

// ==========================================
// Phase 3 Voice & Prosody Engine Interfaces
// ==========================================

export type MicrophoneStatus = 'CONNECTED' | 'DISCONNECTED' | 'MUTED' | 'ERROR';
export type AudioQuality = 'GOOD' | 'NOISY' | 'DEGRADED' | 'SILENCE';
export type CanonicalCommand =
  | 'FORWARD'
  | 'BACKWARD'
  | 'LEFT'
  | 'RIGHT'
  | 'STOP'
  | 'UNKNOWN'
  | 'UNCERTAIN';
export type SemanticStatus = 'VALID' | 'UNCERTAIN' | 'UNKNOWN' | 'REJECTED';

export interface VoiceEvent {
  event_id: string;
  timestamp: number;
  timestamp_event_ms?: number;
  timestamp_proc_ms?: number;
  source: 'voice';
  operator_id?: string;
  transcript: string;
  normalized_transcript: string;
  recognized_command: CanonicalCommand;
  classified_command?: string;
  recognition_confidence: number;
  classification_confidence: number;
  confidence?: number;
  semantic_status: SemanticStatus;
  is_uncertain: boolean;
  direction_vector: { x: number; y: number };
  audio_duration_ms: number;
  pitch_f0: number;
  pitch_f0_std: number;
  jitter: number;
  shimmer: number;
  speech_rate: number;
  intensity: number;
  audio_quality: AudioQuality;
  model_version: string;
  composite_stress_score: number;
  stress_score?: number;
  is_stressed: boolean;
}

export interface VoiceSystemStatus {
  microphone_status: MicrophoneStatus;
  is_capturing: boolean;
  is_muted: boolean;
  selected_device_index?: number | null;
  selected_device_name?: string | null;
  model_name: string;
  model_loaded: boolean;
  language: string;
  sample_rate: number;
  last_event?: VoiceEvent | null;
  error_message?: string | null;
}

export interface AudioDevice {
  index: number;
  name: string;
  hostapi: number | string;
  max_input_channels: number;
  default_samplerate: number;
  is_default: boolean;
}

// ==========================================
// Phase 4 Event Synchronization Interfaces
// ==========================================

export type SynchronizationStatus =
  | 'SYNCHRONIZED'
  | 'VOICE_ONLY'
  | 'JOYSTICK_ONLY'
  | 'OUT_OF_WINDOW'
  | 'DELAYED'
  | 'STALE'
  | 'INVALID_TIMESTAMP'
  | 'DUPLICATE';

export interface CorrelatedEvent {
  correlation_id: string;
  sync_id?: string;
  correlation_timestamp: number;
  timestamp_ms?: number;
  voice_event_id?: string | null;
  joystick_event_id?: string | null;
  voice_command?: string | null;
  joystick_direction?: string | null;
  joystick_intensity?: number | null;
  timestamp_difference_ms?: number | null;
  temporal_delta_ms?: number | null;
  synchronization_status: SynchronizationStatus;
  voice_available: boolean;
  joystick_available: boolean;
  correlation_reason: string;
  voice_event?: VoiceEvent | null;
  joystick_event?: CommonJoystickEvent | null;
  context?: {
    current_velocity?: number;
    nearest_obstacle_m?: number;
    [key: string]: any;
  };
}

export interface SyncEngineStatus {
  sync_window_ms: number;
  max_event_age_ms: number;
  voice_buffer_count: number;
  joystick_buffer_count: number;
  total_synchronized_count: number;
  total_voice_only_count: number;
  total_joystick_only_count: number;
  total_out_of_window_count: number;
  total_delayed_count: number;
  total_stale_count: number;
  total_duplicate_count: number;
  total_invalid_timestamp_count: number;
  last_correlation?: CorrelatedEvent | null;
  voice_pipeline_active: boolean;
  joystick_pipeline_active: boolean;
}

export interface SystemStatusPayload {
  status: 'operational' | 'initializing' | 'error';
  phase: string;
  version: string;
  backendConnected: boolean;
  hardwareDetected: boolean;
  activeSafetyState: SafetyState;
  details?: {
    activeJoystickMode?: string;
    connectedControllers?: number;
    crsThreshold?: number;
    hardwareIsolationEnforced?: boolean;
    microphoneStatus?: string;
    microphoneDevice?: string;
    whisperModel?: string;
    whisperLoaded?: boolean;
    syncWindowMs?: number;
    totalSynchronized?: number;
    [key: string]: any;
  };
}


// ==========================================
// Phase 5 Fusion Engine & CRS Interfaces
// ==========================================

export type CRSStatus = 'COMPLETE' | 'PROVISIONAL' | 'INCOMPLETE' | 'INVALID';

export type AnalyticalFinding =
  | 'AGREEMENT'
  | 'CONTRADICTION'
  | 'UNKNOWN_COMMAND'
  | 'UNCERTAIN_COMMAND'
  | 'NEUTRAL_JOYSTICK'
  | 'INSUFFICIENT_EVIDENCE'
  | 'CONTEXT_UNAVAILABLE'
  | 'CONTEXT_VIOLATION';

export type MissionMode =
  | 'NORMAL'
  | 'RESTRICTED'
  | 'PRECISION'
  | 'EMERGENCY_STOP'
  | 'DOCKED'
  | 'MAINTENANCE';

export interface MovementConstraint {
  constraint_id: string;
  description: string;
  forbidden_directions: string[];
  max_intensity: number;
  is_active: boolean;
}

export interface ContextState {
  operating_mode: MissionMode;
  permitted_directions: string[];
  nearest_obstacle_distance_m: number;
  obstacle_direction?: string | null;
  stopping_distance_threshold_m: number;
  max_admissible_linear_velocity: number;
  current_linear_velocity: number;
  context_confidence: number;
  is_available: boolean;
  timestamp_ms: number;
  context_source: string;
  active_constraints: MovementConstraint[];
}

export interface FusionFactors {
  semantic_score: number;
  motor_agreement: number;
  context_consistency: number;
  angular_delta_deg?: number | null;
  cosine_similarity?: number | null;
  sync_quality: number;
}

export interface FusionResult {
  fusion_id: string;
  correlation_id: string;
  sync_id?: string;
  timestamp: number;
  timestamp_ms?: number;
  voice_command?: string | null;
  joystick_direction?: string | null;
  joystick_intensity?: number | null;
  semantic_reliability: number;
  motor_agreement: number;
  context_consistency: number;
  factors: FusionFactors;
  CRS: number;
  crs_score?: number;
  CRS_status: CRSStatus;
  contradiction_detected: boolean;
  veto_asserted?: boolean;
  contradiction_reason?: string | null;
  synchronization_status: string;
  temporal_delta_ms?: number | null;
  evidence_completeness: number;
  missing_components: string[];
  scoring_config_version: string;
  weights: Record<string, number>;
  explanation: string;
  analytical_finding: AnalyticalFinding;
  recommended_state?: 'GREEN' | 'YELLOW' | 'RED' | string | null;
}

export interface FusionConfig {
  weight_semantic: number;
  weight_motor: number;
  weight_context: number;
  stress_damping: number;
  contradiction_cap: number;
  contradiction_whisper_min: number;
  contradiction_joystick_min: number;
  joystick_deadzone: number;
  scoring_config_version: string;
}

export interface FusionEngineStatus {
  is_active: boolean;
  total_evaluations: number;
  total_agreements: number;
  total_contradictions: number;
  average_crs: number;
  last_crs?: number | null;
  last_status?: CRSStatus | null;
  scoring_config_version: string;
  weights: Record<string, number>;
}


// ==========================================
// Phase 6 Tiered Safety Authorization Types
// ==========================================

export type AuthorizationState = 'GREEN' | 'YELLOW' | 'RED' | 'EMERGENCY';
export type AuthorizationDecision =
  | 'AUTHORIZED'
  | 'HOLD_PENDING_CONFIRMATION'
  | 'REJECTED'
  | 'EMERGENCY_HALT';
export type ConfirmationAction = 'CONFIRM' | 'REJECT';
export type EmergencySource = 'SOFTWARE_UI' | 'HARDWARE_BUTTON' | 'SYSTEM_INTERRUPT';

export interface SafetyDecision {
  decision_id: string;
  fusion_id?: string | null;
  correlation_id?: string | null;
  timestamp_ms: number;
  authorization_state: AuthorizationState;
  authorization_decision: AuthorizationDecision;
  requested_command?: string | null;
  authorized_command?: string | null;
  crs_score?: number | null;
  crs_status?: string | null;
  evidence_completeness: number;
  contradiction_detected: boolean;
  reason: string;
  auth_token?: string | null;
  expires_at_ms?: number | null;
  confirmation_id?: string | null;
  confirmation_timeout_ms?: number | null;
  is_confirmed?: boolean | null;
  confirmed_by?: string | null;
  is_latched: boolean;
  is_simulation: boolean;
}

export interface SafetyEngineStatus {
  active_state: AuthorizationState;
  is_emergency_latched: boolean;
  emergency_source?: EmergencySource | null;
  emergency_timestamp_ms?: number | null;
  pending_confirmations_count: number;
  total_decisions: number;
  total_green: number;
  total_yellow: number;
  total_red: number;
  total_emergency: number;
  green_threshold: number;
  yellow_threshold: number;
  last_decision?: SafetyDecision | null;
}

export interface GatewayExecutionRecord {
  execution_id: string;
  decision_id: string;
  command: string;
  accepted: boolean;
  timestamp_ms: number;
  reason: string;
  auth_token?: string | null;
}


// ==========================================
// Phase 7 Robot Simulation & Execution Types
// ==========================================

export type ExecutionResultType =
  | 'AUTHORIZED'
  | 'EXECUTED'
  | 'HELD'
  | 'REJECTED'
  | 'CANCELLED'
  | 'EMERGENCY_STOPPED';

export interface RobotPose {
  x: number;
  y: number;
  heading_deg: number;
  linear_speed: number;
  angular_speed: number;
}

export interface SimulationObstacle {
  id: string;
  x: number;
  y: number;
  radius: number;
  label: string;
}

export interface SimulationConfig {
  boundary_min_x: number;
  boundary_max_x: number;
  boundary_min_y: number;
  boundary_max_y: number;
  base_speed: number;
  turn_speed_deg: number;
  tick_rate_hz: number;
  robot_radius: number;
}

export interface CommandExecutionRecord {
  command_id: string;
  decision_id: string;
  timestamp_ms: number;
  requested_command: string;
  authorized_command?: string | null;
  crs?: number | null;
  authorization_state: AuthorizationState;
  execution_result: ExecutionResultType;
  rejection_reason?: string | null;
  pose_before: RobotPose;
  pose_after: RobotPose;
}

export interface SimulationState {
  pose: RobotPose;
  active_command: string;
  authorization_state: AuthorizationState;
  is_running: boolean;
  is_paused: boolean;
  is_collision: boolean;
  collision_object?: string | null;
  boundary_hit: boolean;
  speed_multiplier: number;
  timestamp_ms: number;
  step_count: number;
  trajectory: [number, number][];
  obstacles: SimulationObstacle[];
  last_rejected_command?: string | null;
  last_rejection_reason?: string | null;
  voice_command?: string | null;
  joystick_direction?: string | null;
  crs?: number | null;
}

export interface SimulationControlRequest {
  action: 'START' | 'PAUSE' | 'RESUME' | 'RESET' | 'SET_SPEED';
  speed_multiplier?: number;
  reset_x?: number;
  reset_y?: number;
}


// ==========================================
// Phase 8 Complete System Integration Types
// ==========================================

export interface SystemOverviewPayload {
  timestamp_ms: number;
  operating_mode: string;
  simulation_only_enforced: boolean;
  active_operator: string;
  backend_connected: boolean;
  active_safety_state: AuthorizationState;
  voice: {
    status: MicrophoneStatus;
    device?: string | null;
    model: string;
    is_calibrated: boolean;
    last_transcript?: string | null;
    last_command?: string | null;
  };
  joystick: {
    mode: JoystickMode;
    hardware_detected: boolean;
    connection_status: ConnectionStatus;
    primary_device?: string | null;
    direction: JoystickDirection;
    intensity: number;
  };
  synchronization: {
    is_running: boolean;
    sync_window_ms: number;
    total_synchronized: number;
    voice_buffer_size: number;
    joystick_buffer_size: number;
  };
  fusion: {
    is_active: boolean;
    total_evaluations: number;
    average_crs: number;
    last_crs?: number | null;
    contradiction_count: number;
  };
  safety: {
    state: AuthorizationState;
    is_emergency_latched: boolean;
    pending_confirmations: number;
    total_authorized: number;
    total_rejected: number;
    total_emergency: number;
  };
  simulation: {
    is_running: boolean;
    is_paused: boolean;
    active_command: string;
    x: number;
    y: number;
    heading: number;
    linear_speed: number;
    speed_multiplier: number;
    is_collision: boolean;
    boundary_hit: boolean;
  };
}

export interface ServiceDiagnostic {
  status: 'HEALTHY' | 'DEGRADED' | 'DISCONNECTED' | 'STOPPED' | 'ERROR' | 'UNKNOWN' | string;
  [key: string]: any;
}

export interface DetailedHealthPayload {
  status: string;
  diagnostic_latency_ms: number;
  timestamp_ms: number;
  services: {
    backend_core: ServiceDiagnostic;
    voice_service: ServiceDiagnostic;
    joystick_service: ServiceDiagnostic;
    sync_service: ServiceDiagnostic;
    fusion_service: ServiceDiagnostic;
    safety_gateway: ServiceDiagnostic;
    robot_simulator: ServiceDiagnostic;
    database_persistence: ServiceDiagnostic;
  };
}

export interface ParameterMetadata {
  label: string;
  unit: string;
  default: number | string | boolean;
  is_experimental: boolean;
  description: string;
}

export interface SystemConfigPayload {
  parameters: {
    sync_window_ms: number;
    joystick_deadzone: number;
    voice_confidence_threshold: number;
    crs_weight_semantic: number;
    crs_weight_motor: number;
    crs_weight_context: number;
    safety_green_threshold: number;
    safety_yellow_threshold: number;
    simulation_speed: number;
    prosody_stress_damping: number;
  };
  metadata: Record<string, ParameterMetadata>;
}

export interface AuditLogEntry {
  id: number;
  event_id: string;
  timestamp_ms: number;
  iso_time: string;
  category: string;
  command?: string | null;
  safety_state?: string | null;
  execution_result?: string | null;
  crs?: number | null;
  details_json?: string | null;
  details: Record<string, any>;
}

export interface AuditLogQueryFilter {
  category?: string;
  safety_state?: string;
  command?: string;
  execution_result?: string;
  limit?: number;
  offset?: number;
}
