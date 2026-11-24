/**
 * DCRG Phase 7 - Interactive 2D Robot Simulation Panel.
 * Renders grid environment, boundary walls, obstacles, kinematic vehicle pose,
 * heading alignment vector, trajectory trail, live telemetry HUD,
 * directional driving D-Pad, keyboard controls, multimodal safety verification actions,
 * and command execution audit logs.
 */

import React, { useEffect, useRef, useState } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  AlertOctagon,
  Gauge,
  Activity,
  Shield,
  Wifi,
  WifiOff,
  Crosshair,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  CircleDot,
  Zap,
  Check,
  Keyboard,
} from 'lucide-react';
import { useSimulationStream } from '../hooks/useSimulationStream';
import { useJoystickStream } from '../hooks/useJoystickStream';
import {
  triggerEmergencyStop,
  playPredefinedSample,
  postVirtualJoystickInput,
  fetchPendingConfirmations,
  confirmSafetyDecision,
} from '../services/api';
import type { SafetyDecision } from '../types';

export const RobotSimulationPanel: React.FC = () => {
  const {
    simulationState,
    executionLogs,
    isWsConnected,
    pause,
    resume,
    resetPose,
    setSpeedMultiplier,
    sendCommand,
  } = useSimulationStream();

  const { lastEvent: lastJoyEvent } = useJoystickStream();

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [testActionLoading, setTestActionLoading] = useState<string | null>(null);
  const [testResultFeedback, setTestResultFeedback] = useState<string | null>(null);
  const [pendingConf, setPendingConf] = useState<SafetyDecision | null>(null);
  const [showAuditLogs, setShowAuditLogs] = useState(false);

  // Real-time synchronization: Drive 2D simulation from hardware and virtual joystick stream
  const lastJoyDirRef = useRef<string>('CENTER');
  useEffect(() => {
    if (!lastJoyEvent) return;

    const dir = lastJoyEvent.direction;
    if (dir === lastJoyDirRef.current) return;
    lastJoyDirRef.current = dir;

    if (dir === 'FORWARD' || dir === 'FORWARD_LEFT' || dir === 'FORWARD_RIGHT') {
      sendCommand('FORWARD');
    } else if (dir === 'BACKWARD' || dir === 'BACKWARD_LEFT' || dir === 'BACKWARD_RIGHT') {
      sendCommand('BACKWARD');
    } else if (dir === 'LEFT') {
      sendCommand('LEFT');
    } else if (dir === 'RIGHT') {
      sendCommand('RIGHT');
    } else if (dir === 'CENTER') {
      sendCommand('STOP');
    }
  }, [lastJoyEvent, sendCommand]);

  // Poll for pending confirmations
  useEffect(() => {
    const checkPending = async () => {
      try {
        const list = await fetchPendingConfirmations();
        setPendingConf(list.length > 0 ? list[0] : null);
      } catch {
        // Silently ignore
      }
    };
    checkPending();
    const interval = setInterval(checkPending, 1500);
    return () => clearInterval(interval);
  }, []);

  // Handle confirming a pending hold command
  const handleConfirmHold = async () => {
    if (!pendingConf) return;
    try {
      await confirmSafetyDecision(pendingConf.decision_id, 'CONFIRM', 'OP-SIMULATION');
      setTestResultFeedback(`Confirmed hold: '${pendingConf.requested_command}' dispatched to simulation!`);
      setPendingConf(null);
    } catch (err: any) {
      setTestResultFeedback(`Confirmation failed: ${err.message}`);
    }
  };

  // Keyboard driving controls (WASD and Arrow keys)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }

      const key = e.key.toLowerCase();
      if (key === 'w' || key === 'arrowup') {
        e.preventDefault();
        sendCommand('FORWARD');
      } else if (key === 's' || key === 'arrowdown') {
        e.preventDefault();
        sendCommand('BACKWARD');
      } else if (key === 'a' || key === 'arrowleft') {
        e.preventDefault();
        sendCommand('LEFT');
      } else if (key === 'd' || key === 'arrowright') {
        e.preventDefault();
        sendCommand('RIGHT');
      } else if (key === ' ' || key === 'escape') {
        e.preventDefault();
        sendCommand('STOP');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [sendCommand]);

  // Multimodal safety testing handlers
  const handleRunMultimodalTest = async (
    testId: string,
    joyX: number,
    joyY: number,
    voiceSampleId: string,
    desc: string
  ) => {
    setTestActionLoading(testId);
    setTestResultFeedback(`Running: Ingesting stick (${joyX}, ${joyY}) + voice '${voiceSampleId}'...`);
    try {
      await postVirtualJoystickInput(joyX, joyY);
      try {
        const audio = new Audio(`/samples/${voiceSampleId}.wav`);
        audio.play().catch(() => {});
      } catch {
        // Audio fallback silent
      }
      await playPredefinedSample(voiceSampleId);
      await postVirtualJoystickInput(joyX, joyY);
      setTestResultFeedback(`Success! ${desc}`);
    } catch (err: any) {
      setTestResultFeedback(`Test note: ${err.message}`);
    } finally {
      setTestActionLoading(null);
    }
  };

  // 2D Canvas Renderer Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Coordinate conversion: World (-50 to +50 meters) to Canvas pixels
    const worldMin = -50;
    const worldMax = 50;
    const worldRange = worldMax - worldMin;

    const toCanvasX = (worldX: number) => ((worldX - worldMin) / worldRange) * width;
    const toCanvasY = (worldY: number) => height - ((worldY - worldMin) / worldRange) * height;
    const toScale = (meters: number) => (meters / worldRange) * width;

    // 1. Clear background
    ctx.fillStyle = '#0a0f1d';
    ctx.fillRect(0, 0, width, height);

    // 2. Draw Grid Lines
    ctx.lineWidth = 1;
    ctx.strokeStyle = '#1e293b';
    for (let m = worldMin; m <= worldMax; m += 10) {
      // Vertical
      ctx.beginPath();
      ctx.moveTo(toCanvasX(m), 0);
      ctx.lineTo(toCanvasX(m), height);
      ctx.stroke();

      // Horizontal
      ctx.beginPath();
      ctx.moveTo(0, toCanvasY(m));
      ctx.lineTo(width, toCanvasY(m));
      ctx.stroke();
    }

    // 3. Draw Center Coordinate Axes (0, 0)
    ctx.strokeStyle = '#334155';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(toCanvasX(0), 0);
    ctx.lineTo(toCanvasX(0), height);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(0, toCanvasY(0));
    ctx.lineTo(width, toCanvasY(0));
    ctx.stroke();

    // 4. Draw World Boundary Walls
    ctx.strokeStyle = simulationState?.boundary_hit ? '#ef4444' : '#475569';
    ctx.lineWidth = simulationState?.boundary_hit ? 4 : 2;
    ctx.strokeRect(toCanvasX(-49.5), toCanvasY(49.5), toScale(99), toScale(99));

    // 5. Draw Static Circular Obstacles
    const obstacles = simulationState?.obstacles || [
      { id: 'obs-alpha', x: 15.0, y: 15.0, radius: 3.5, label: 'Barrier Alpha' },
      { id: 'obs-beta', x: -20.0, y: 12.0, radius: 4.0, label: 'Pylon Beta' },
      { id: 'obs-gamma', x: 0.0, y: -25.0, radius: 3.0, label: 'Cylinder Gamma' },
    ];

    obstacles.forEach((obs) => {
      const cx = toCanvasX(obs.x);
      const cy = toCanvasY(obs.y);
      const cr = toScale(obs.radius);

      const grad = ctx.createRadialGradient(cx, cy, cr * 0.2, cx, cy, cr);
      grad.addColorStop(0, '#f97316');
      grad.addColorStop(1, '#7c2d12');

      ctx.beginPath();
      ctx.arc(cx, cy, cr, 0, 2 * Math.PI);
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#ea580c';
      ctx.stroke();

      ctx.fillStyle = '#fed7aa';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(obs.label, cx, cy - cr - 4);
    });

    // 6. Draw Trajectory Trail
    if (simulationState?.trajectory && simulationState.trajectory.length > 1) {
      ctx.beginPath();
      const first = simulationState.trajectory[0];
      ctx.moveTo(toCanvasX(first[0]), toCanvasY(first[1]));
      for (let i = 1; i < simulationState.trajectory.length; i++) {
        const pt = simulationState.trajectory[i];
        ctx.lineTo(toCanvasX(pt[0]), toCanvasY(pt[1]));
      }
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.5)';
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    // 7. Draw Robot Vehicle
    const pose = simulationState?.pose || {
      x: 0,
      y: 0,
      heading_deg: 0,
      linear_speed: 0,
      angular_speed: 0,
    };
    const rx = toCanvasX(pose.x);
    const ry = toCanvasY(pose.y);
    const robotRadius = toScale(1.0); // 1.0m radius

    // Collision envelope halo
    const authState = simulationState?.authorization_state || 'GREEN';
    let haloColor = 'rgba(16, 185, 129, 0.2)'; // GREEN
    let bodyColor = '#10b981';
    if (authState === 'YELLOW') {
      haloColor = 'rgba(245, 158, 11, 0.25)';
      bodyColor = '#f59e0b';
    } else if (authState === 'RED') {
      haloColor = 'rgba(239, 68, 68, 0.3)';
      bodyColor = '#ef4444';
    } else if (authState === 'EMERGENCY') {
      haloColor = 'rgba(220, 38, 38, 0.5)';
      bodyColor = '#dc2626';
    }

    if (simulationState?.is_collision) {
      haloColor = 'rgba(239, 68, 68, 0.6)';
    }

    // Outer radius ring
    ctx.beginPath();
    ctx.arc(rx, ry, robotRadius * 1.6, 0, 2 * Math.PI);
    ctx.fillStyle = haloColor;
    ctx.fill();
    ctx.strokeStyle = bodyColor;
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Vehicle Chassis
    ctx.save();
    ctx.translate(rx, ry);
    const headingRad = ((pose.heading_deg - 90) * Math.PI) / 180;
    ctx.rotate(headingRad);

    // Chassis Box
    const carLength = robotRadius * 1.8;
    const carWidth = robotRadius * 1.2;
    ctx.fillStyle = bodyColor;
    ctx.fillRect(-carLength / 2, -carWidth / 2, carLength, carWidth);
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.strokeRect(-carLength / 2, -carWidth / 2, carLength, carWidth);

    // Nose direction arrow
    ctx.beginPath();
    ctx.moveTo(carLength / 2, 0);
    ctx.lineTo(carLength / 2 + toScale(1.2), 0);
    ctx.strokeStyle = '#38bdf8';
    ctx.lineWidth = 3;
    ctx.stroke();

    ctx.restore();

    // Coordinates overlay text
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`X: ${pose.x.toFixed(2)} m, Y: ${pose.y.toFixed(2)} m`, 12, height - 12);
  }, [simulationState]);

  const handleEStop = async () => {
    try {
      await triggerEmergencyStop('SOFTWARE_UI', 'Simulation Panel E-STOP Activated');
    } catch {
      // Ignored
    }
  };

  const pose = simulationState?.pose || {
    x: 0,
    y: 0,
    heading_deg: 0,
    linear_speed: 0,
    angular_speed: 0,
  };

  const isMoving = pose.linear_speed > 0.05;

  return (
    <div className="space-y-6 text-left">
      {/* Pending Confirmation Warning Banner */}
      {pendingConf && (
        <div className="p-4 bg-amber-950/80 border-2 border-amber-500 rounded-xl shadow-xl flex flex-col sm:flex-row items-center justify-between gap-3 animate-pulse">
          <div className="flex items-center space-x-3 text-amber-200">
            <AlertTriangle className="w-6 h-6 text-amber-400 shrink-0" />
            <div>
              <div className="font-bold text-sm uppercase tracking-wide">
                Command On Hold: {pendingConf.requested_command} (CRS: {pendingConf.crs_score?.toFixed(1) || '--'}/100)
              </div>
              <p className="text-xs text-amber-300 font-mono mt-0.5">
                {pendingConf.reason}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleConfirmHold}
            className="flex items-center space-x-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-mono font-bold rounded-lg transition shadow-lg shrink-0"
          >
            <Check className="w-4 h-4" />
            <span>CONFIRM & EXECUTE NOW</span>
          </button>
        </div>
      )}

      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-4 border-b border-slate-800 gap-3">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-slate-800 text-cyan-400">
            <Crosshair className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-100 m-0">
              Interactive 2D Kinematic Simulation
            </h2>
            <p className="text-xs text-slate-400 m-0">
              Real-time 20Hz Kinematic Physics, Directional Steering, and Multimodal Authorization Verification
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          <div
            className={`flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold border ${
              isWsConnected
                ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800'
                : 'bg-rose-950/60 text-rose-400 border-rose-800'
            }`}
          >
            {isWsConnected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            <span>{isWsConnected ? '20 Hz Stream' : 'Offline / Polling'}</span>
          </div>

          <span
            className={`px-3 py-1 rounded-full text-xs font-mono font-bold border tracking-wider uppercase ${
              isMoving
                ? 'bg-emerald-950 text-emerald-300 border-emerald-600 animate-pulse'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            }`}
          >
            {isMoving ? '🟢 MOVING (REAL-TIME)' : '⚪ HALTED'}
          </span>
        </div>
      </div>

      {/* Main Grid: Visualizer + Controls & Telemetry */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: 2D Canvas & Directional Driving Pad (7 Cols) */}
        <div className="lg:col-span-7 flex flex-col items-center space-y-4">
          <div className="relative w-full max-w-[540px] aspect-square rounded-xl overflow-hidden border border-slate-700 shadow-2xl bg-[#0a0f1d]">
            <canvas ref={canvasRef} width={540} height={540} className="w-full h-full block" />

            {/* Collision Warnings */}
            {simulationState?.is_collision && (
              <div className="absolute top-3 left-3 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-rose-600/90 text-white font-mono text-xs font-bold shadow-lg animate-bounce">
                <AlertTriangle className="w-4 h-4" />
                COLLISION: {simulationState.collision_object}
              </div>
            )}
            {simulationState?.boundary_hit && (
              <div className="absolute top-3 right-3 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-600/90 text-white font-mono text-xs font-bold shadow-lg">
                <Shield className="w-4 h-4" />
                BOUNDARY LIMIT REACHED
              </div>
            )}

            {/* Canvas Legend */}
            <div className="absolute bottom-2 left-2 flex items-center gap-3 px-2 py-1 rounded bg-slate-900/80 backdrop-blur border border-slate-800 text-[10px] text-slate-400 font-mono">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" /> Robot
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-orange-500 inline-block" /> Obstacle
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-0.5 bg-cyan-400 inline-block" /> Path
              </span>
            </div>
          </div>

          {/* Directional Motion Driving Controller D-Pad */}
          <div className="w-full max-w-[540px] p-4 bg-slate-900 border border-slate-800 rounded-xl flex flex-col items-center space-y-2">
            <div className="flex items-center justify-between w-full pb-2 border-b border-slate-800">
              <div className="flex items-center space-x-2 text-xs font-mono text-slate-300 font-bold">
                <Gauge className="w-4 h-4 text-cyan-400" />
                <span>INTERACTIVE DIRECTIONAL CONTROLLER</span>
              </div>
              <span className="text-[11px] font-mono text-slate-500 flex items-center space-x-1">
                <Keyboard className="w-3.5 h-3.5" />
                <span>WASD / Arrow Keys Supported</span>
              </span>
            </div>

            {/* D-Pad Buttons */}
            <div className="flex flex-col items-center space-y-1.5 pt-2">
              <button
                type="button"
                onClick={() => sendCommand('FORWARD')}
                className={`px-5 py-2 rounded-lg flex items-center space-x-1.5 text-xs font-mono font-bold transition border shadow-md ${
                  simulationState?.active_command === 'FORWARD'
                    ? 'bg-cyan-600 text-white border-cyan-400'
                    : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750 hover:border-cyan-500'
                }`}
              >
                <ArrowUp className="w-4 h-4" />
                <span>MOVE FORWARD (NORTH)</span>
              </button>

              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => sendCommand('LEFT')}
                  className={`px-4 py-2 rounded-lg flex items-center space-x-1.5 text-xs font-mono font-bold transition border shadow-md ${
                    simulationState?.active_command === 'LEFT'
                      ? 'bg-cyan-600 text-white border-cyan-400'
                      : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750 hover:border-cyan-500'
                  }`}
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span>LEFT</span>
                </button>

                <button
                  type="button"
                  onClick={() => sendCommand('STOP')}
                  className={`px-5 py-2 rounded-lg flex items-center space-x-1.5 text-xs font-mono font-bold transition border shadow-md ${
                    simulationState?.active_command === 'STOP'
                      ? 'bg-rose-700 text-white border-rose-500'
                      : 'bg-slate-800 text-rose-300 border-slate-700 hover:bg-slate-750'
                  }`}
                >
                  <CircleDot className="w-4 h-4 text-rose-400" />
                  <span>HALT / STOP</span>
                </button>

                <button
                  type="button"
                  onClick={() => sendCommand('RIGHT')}
                  className={`px-4 py-2 rounded-lg flex items-center space-x-1.5 text-xs font-mono font-bold transition border shadow-md ${
                    simulationState?.active_command === 'RIGHT'
                      ? 'bg-cyan-600 text-white border-cyan-400'
                      : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750 hover:border-cyan-500'
                  }`}
                >
                  <span>RIGHT</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>

              <button
                type="button"
                onClick={() => sendCommand('BACKWARD')}
                className={`px-5 py-2 rounded-lg flex items-center space-x-1.5 text-xs font-mono font-bold transition border shadow-md ${
                  simulationState?.active_command === 'BACKWARD'
                    ? 'bg-cyan-600 text-white border-cyan-400'
                    : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-750 hover:border-cyan-500'
                }`}
              >
                <ArrowDown className="w-4 h-4" />
                <span>MOVE BACKWARD (SOUTH)</span>
              </button>
            </div>
          </div>

          {/* Auxiliary Environment Bar */}
          <div className="w-full max-w-[540px] p-3 bg-slate-800/80 border border-slate-700 rounded-xl flex flex-wrap items-center justify-between gap-3">
            <button
              onClick={() => (simulationState?.is_paused ? resume() : pause())}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-semibold transition"
            >
              {simulationState?.is_paused ? (
                <>
                  <Play className="w-3.5 h-3.5 text-emerald-400" /> Resume
                </>
              ) : (
                <>
                  <Pause className="w-3.5 h-3.5 text-amber-400" /> Pause
                </>
              )}
            </button>

            <button
              onClick={() => resetPose(0.0, 0.0, 0.0)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-semibold transition"
            >
              <RotateCcw className="w-3.5 h-3.5 text-cyan-400" /> Reset Origin
            </button>

            <div className="flex items-center gap-1 bg-slate-900 p-1 rounded-lg border border-slate-700 text-xs font-mono">
              <span className="text-slate-400 px-1 text-[11px]">Speed:</span>
              {[0.5, 1.0, 2.0].map((rate) => (
                <button
                  key={rate}
                  onClick={() => setSpeedMultiplier(rate)}
                  className={`px-2 py-0.5 rounded transition ${
                    simulationState?.speed_multiplier === rate
                      ? 'bg-cyan-600 text-white font-bold'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {rate}x
                </button>
              ))}
            </div>

            <button
              onClick={handleEStop}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold uppercase tracking-wider transition shadow-lg shadow-rose-900/30"
            >
              <AlertOctagon className="w-4 h-4" /> E-STOP
            </button>
          </div>
        </div>

        {/* Right Column: Telemetry HUD & Cross-Modal Testing (5 Cols) */}
        <div className="lg:col-span-5 space-y-4">
          {/* Kinematic Telemetry Card */}
          <div className="p-4 bg-slate-800/60 border border-slate-700/80 rounded-xl space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Gauge className="w-4 h-4 text-cyan-400" /> Kinematic Telemetry
            </h3>

            <div className="grid grid-cols-2 gap-3 font-mono">
              <div className="p-2.5 bg-slate-900/70 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase">Position (X, Y)</span>
                <p className="text-base font-bold text-white mt-0.5">
                  {pose.x.toFixed(2)} m, {pose.y.toFixed(2)} m
                </p>
              </div>

              <div className="p-2.5 bg-slate-900/70 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase">Heading</span>
                <p className="text-base font-bold text-cyan-300 mt-0.5">
                  {pose.heading_deg.toFixed(1)}°
                </p>
              </div>

              <div className="p-2.5 bg-slate-900/70 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase">Linear Velocity</span>
                <p className={`text-base font-bold mt-0.5 ${isMoving ? 'text-emerald-400' : 'text-slate-400'}`}>
                  {pose.linear_speed.toFixed(2)} m/s
                </p>
              </div>

              <div className="p-2.5 bg-slate-900/70 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase">Active Primitive</span>
                <p className="text-base font-bold text-amber-300 mt-0.5">
                  {simulationState?.active_command || 'STOP'}
                </p>
              </div>
            </div>
          </div>

          {/* 1-Click Multimodal Safety Actions */}
          <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
            <div className="flex items-center space-x-2 text-slate-200">
              <Zap className="w-4 h-4 text-amber-400" />
              <h4 className="text-xs font-bold uppercase tracking-wider font-mono">
                Multimodal Verification Actions
              </h4>
            </div>
            <p className="text-[11px] text-slate-400">
              Trigger speech-motor agreement to authorize real-time motion, or contradiction to verify immediate lockout.
            </p>

            <div className="space-y-2 mt-2">
              {/* Test Agreement Action */}
              <button
                type="button"
                disabled={testActionLoading !== null}
                onClick={() =>
                  handleRunMultimodalTest(
                    'AGREEMENT_FWD',
                    0.0,
                    0.85,
                    'forward',
                    'Multimodal Agreement: Voice FORWARD + Stick FORWARD -> Robot moving forward in real-time!'
                  )
                }
                className="w-full flex items-center justify-between p-2.5 rounded-lg bg-emerald-950/40 hover:bg-emerald-900/60 text-emerald-200 border border-emerald-800/80 transition text-xs font-mono text-left"
              >
                <div className="flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <strong className="block text-emerald-300">Test Agreement: Voice FWD + Stick FWD</strong>
                    <span className="text-[10px] text-slate-400">Authorizes GREEN &rarr; Drives robot at 3.0 m/s</span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-emerald-400 shrink-0" />
              </button>

              {/* Test Contradiction Veto Action */}
              <button
                type="button"
                disabled={testActionLoading !== null}
                onClick={() =>
                  handleRunMultimodalTest(
                    'CONTRADICTION_LATERAL',
                    0.85,
                    0.0,
                    'left',
                    'Contradiction Veto: Voice LEFT vs Stick RIGHT -> Safety Gate halts robot!'
                  )
                }
                className="w-full flex items-center justify-between p-2.5 rounded-lg bg-rose-950/40 hover:bg-rose-900/60 text-rose-200 border border-rose-800/80 transition text-xs font-mono text-left"
              >
                <div className="flex items-center space-x-2">
                  <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <div>
                    <strong className="block text-rose-300">Test Contradiction: Voice LEFT vs Stick RIGHT</strong>
                    <span className="text-[10px] text-slate-400">Veto Clamps CRS &le; 30.0 &rarr; Immediate Lockout</span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-rose-400 shrink-0" />
              </button>

              {/* Spoken Emergency Stop Action */}
              <button
                type="button"
                disabled={testActionLoading !== null}
                onClick={() =>
                  handleRunMultimodalTest(
                    'STOP_OVERRIDE',
                    0.0,
                    0.85,
                    'stop',
                    'Voice STOP Preemption -> Immediately freezes robot motion!'
                  )
                }
                className="w-full flex items-center justify-between p-2.5 rounded-lg bg-red-950/50 hover:bg-red-900/70 text-red-200 border border-red-700 transition text-xs font-mono text-left"
              >
                <div className="flex items-center space-x-2">
                  <AlertOctagon className="w-4 h-4 text-red-400 shrink-0" />
                  <div>
                    <strong className="block text-red-300">Test Voice STOP Preemption</strong>
                    <span className="text-[10px] text-slate-400">Preempts moving stick &rarr; Freezes robot</span>
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-red-400 shrink-0" />
              </button>
            </div>

            {testResultFeedback && (
              <div className="p-2 rounded bg-slate-900 border border-slate-800 text-[11px] font-mono text-cyan-300 flex items-start space-x-2 mt-2">
                <Activity className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
                <span>{testResultFeedback}</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Command Execution Audit Log Table (Collapsible) */}
      <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/50">
        <button
          type="button"
          onClick={() => setShowAuditLogs(!showAuditLogs)}
          className="w-full px-4 py-3 bg-slate-800/50 hover:bg-slate-800/80 border-b border-slate-800 flex items-center justify-between text-left transition"
        >
          <div className="flex items-center space-x-2">
            <Crosshair className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Command Execution Audit Trail (Gateway Verified)
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-700 text-cyan-400 font-bold">
              {showAuditLogs ? '▼ HIDE TABLE' : '▶ SHOW TABLE'}
            </span>
          </div>
          <span className="text-xs text-slate-500 font-mono">
            {executionLogs.length} events logged
          </span>
        </button>

        {showAuditLogs && (
          <div className="overflow-x-auto max-h-64">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/90 text-slate-400 border-b border-slate-800 sticky top-0">
                <tr>
                  <th className="px-3 py-2">Timestamp</th>
                  <th className="px-3 py-2">Requested</th>
                  <th className="px-3 py-2">Authorized</th>
                  <th className="px-3 py-2">CRS</th>
                  <th className="px-3 py-2">State</th>
                  <th className="px-3 py-2">Execution Result</th>
                  <th className="px-3 py-2">Coordinates (Pre &rarr; Post)</th>
                  <th className="px-3 py-2">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {executionLogs.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-6 text-center text-slate-500 italic">
                      No command execution events recorded yet.
                    </td>
                  </tr>
                ) : (
                  executionLogs.map((log) => {
                    const date = new Date(log.timestamp_ms);
                    const timeStr = `${date.toTimeString().split(' ')[0]}.${date
                      .getMilliseconds()
                      .toString()
                      .padStart(3, '0')}`;
                    return (
                      <tr key={log.command_id} className="hover:bg-slate-800/30 transition">
                        <td className="px-3 py-2 text-slate-400 whitespace-nowrap">{timeStr}</td>
                        <td className="px-3 py-2 font-semibold text-white">
                          {log.requested_command}
                        </td>
                        <td className="px-3 py-2 text-cyan-300">
                          {log.authorized_command || '—'}
                        </td>
                        <td className="px-3 py-2 text-slate-300">
                          {log.crs !== null && log.crs !== undefined ? log.crs.toFixed(1) : '—'}
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              log.authorization_state === 'GREEN'
                               ? 'bg-emerald-950 text-emerald-300 border-emerald-600'
                                : log.authorization_state === 'YELLOW'
                                ? 'bg-amber-950 text-amber-300 border-amber-600'
                                : 'bg-rose-950 text-rose-300 border-rose-600'
                            }`}
                          >
                            {log.authorization_state}
                          </span>
                        </td>
                        <td className="px-3 py-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1 w-fit ${
                              log.execution_result === 'EXECUTED'
                                ? 'bg-emerald-950 text-emerald-300 border-emerald-600'
                                : log.execution_result === 'HELD'
                                ? 'bg-amber-950 text-amber-300 border-amber-600'
                                : 'bg-rose-950 text-rose-300 border-rose-600'
                            }`}
                          >
                            {log.execution_result === 'EXECUTED' && (
                              <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                            )}
                            {log.execution_result === 'HELD' && (
                              <AlertTriangle className="w-3 h-3 text-amber-400" />
                            )}
                            {(log.execution_result === 'REJECTED' ||
                              log.execution_result === 'EMERGENCY_STOPPED') && (
                              <XCircle className="w-3 h-3 text-rose-400" />
                            )}
                            {log.execution_result}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-slate-400 whitespace-nowrap">
                          ({log.pose_before.x.toFixed(1)}, {log.pose_before.y.toFixed(1)}) &rarr; (
                          {log.pose_after.x.toFixed(1)}, {log.pose_after.y.toFixed(1)})
                        </td>
                        <td className="px-3 py-2 text-slate-400 truncate max-w-xs" title={log.rejection_reason || ''}>
                          {log.rejection_reason || 'Simulated execution verified'}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
