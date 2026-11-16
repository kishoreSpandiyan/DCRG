/**
 * DCRG Phase 7 - Interactive 2D Robot Simulation Panel.
 * Renders grid environment, boundary walls, obstacles, kinematic vehicle pose,
 * heading alignment vector, trajectory trail, live telemetry HUD,
 * simulation controls, and command execution audit logs.
 */

import React, { useEffect, useRef } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  AlertOctagon,
  Compass,
  Gauge,
  Activity,
  Shield,
  Wifi,
  WifiOff,
  Crosshair,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import { useSimulationStream } from '../hooks/useSimulationStream';
import { triggerEmergencyStop } from '../services/api';
import type { AuthorizationState, ExecutionResultType } from '../types';

export const RobotSimulationPanel: React.FC = () => {
  const {
    simulationState,
    executionLogs,
    isWsConnected,
    pause,
    resume,
    resetPose,
    setSpeedMultiplier,
  } = useSimulationStream();

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

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
    // Canvas Y is inverted: +Y is upward in world coordinates
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

      // Gradient fill
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

      // Label
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
      ctx.strokeStyle = 'rgba(6, 182, 212, 0.4)';
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

    // Vehicle Chassis (oriented rotated rectangle)
    ctx.save();
    ctx.translate(rx, ry);
    // Heading: 0 = North (-Y in canvas), 90 = East (+X), 180 = South (+Y), 270 = West (-X)
    // Canvas rotation: 0 radians points along +X, so North is -PI/2 radians
    const headingRad = ((pose.heading_deg - 90) * Math.PI) / 180;
    ctx.rotate(headingRad);

    // Chassis Box
    const carLength = robotRadius * 1.8;
    const carWidth = robotRadius * 1.2;
    ctx.fillStyle = bodyColor;
    ctx.beginPath();
    ctx.roundRect(-carLength / 2, -carWidth / 2, carLength, carWidth, 4);
    ctx.fill();
    ctx.strokeStyle = '#ffffff';
    ctx.lineWidth = 1.5;
    ctx.stroke();

    // Front Nose Direction Indicator Arrow
    ctx.fillStyle = '#ffffff';
    ctx.beginPath();
    ctx.moveTo(carLength / 2 + 6, 0);
    ctx.lineTo(carLength / 2 - 2, -4);
    ctx.lineTo(carLength / 2 - 2, 4);
    ctx.closePath();
    ctx.fill();

    ctx.restore();

    // Coordinates Tag beside robot
    ctx.fillStyle = '#94a3b8';
    ctx.font = '11px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`(${pose.x.toFixed(1)}, ${pose.y.toFixed(1)})`, rx + 14, ry - 14);
  }, [simulationState]);

  // Authorization state badge styling
  const getBadgeStyle = (state?: AuthorizationState) => {
    switch (state) {
      case 'GREEN':
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40';
      case 'YELLOW':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/40';
      case 'RED':
        return 'bg-rose-500/20 text-rose-400 border-rose-500/40';
      case 'EMERGENCY':
        return 'bg-red-600/30 text-red-400 border-red-500 font-bold animate-pulse';
      default:
        return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  const getResultBadgeStyle = (result: ExecutionResultType) => {
    switch (result) {
      case 'EXECUTED':
      case 'AUTHORIZED':
        return 'bg-emerald-950 text-emerald-400 border-emerald-800';
      case 'HELD':
        return 'bg-amber-950 text-amber-400 border-amber-800';
      case 'REJECTED':
      case 'CANCELLED':
        return 'bg-rose-950 text-rose-400 border-rose-800';
      case 'EMERGENCY_STOPPED':
        return 'bg-red-950 text-red-400 border-red-800 font-bold';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  const handleEStop = async () => {
    try {
      await triggerEmergencyStop('SOFTWARE_UI', 'Emergency stop from Simulation Panel');
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

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6">
      {/* Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-cyan-500/10 rounded-lg border border-cyan-500/20">
            <Compass className="w-6 h-6 text-cyan-400 animate-spin-slow" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide flex items-center gap-2">
              Robot Simulation & Command Execution
              <span className="text-xs px-2 py-0.5 rounded-full bg-cyan-900/60 text-cyan-300 border border-cyan-700 font-mono">
                Phase 7
              </span>
            </h2>
            <p className="text-sm text-slate-400">
              Interactive 2D kinematics, boundary checks, and safety-gated dispatching
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono border ${
              isWsConnected
                ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800'
                : 'bg-rose-950/60 text-rose-400 border-rose-800'
            }`}
          >
            {isWsConnected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
            <span>{isWsConnected ? '20 Hz Stream' : 'Offline / Polling'}</span>
          </div>

          <span
            className={`px-3 py-1 rounded-full text-xs font-bold border tracking-wider uppercase ${getBadgeStyle(
              simulationState?.authorization_state
            )}`}
          >
            {simulationState?.authorization_state || 'GREEN'}
          </span>
        </div>
      </div>

      {/* Main Grid: Visualizer + Telemetry HUD */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: 2D Canvas Visualizer (7 Cols) */}
        <div className="lg:col-span-7 flex flex-col items-center">
          <div className="relative w-full max-w-[540px] aspect-square rounded-xl overflow-hidden border border-slate-700 shadow-2xl bg-[#0a0f1d]">
            <canvas
              ref={canvasRef}
              width={540}
              height={540}
              className="w-full h-full block"
            />

            {/* Warning Overlays */}
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

          {/* Interactive Controls Bar */}
          <div className="w-full max-w-[540px] mt-4 p-3 bg-slate-800/80 border border-slate-700 rounded-xl flex flex-wrap items-center justify-between gap-3">
            {/* Pause / Resume */}
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

            {/* Reset Coordinates */}
            <button
              onClick={() => resetPose(0.0, 0.0, 0.0)}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 text-xs font-semibold transition"
            >
              <RotateCcw className="w-3.5 h-3.5 text-cyan-400" /> Reset Origin
            </button>

            {/* Speed Multiplier */}
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

            {/* Emergency Stop Button */}
            <button
              onClick={handleEStop}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-bold uppercase tracking-wider transition shadow-lg shadow-rose-900/30"
            >
              <AlertOctagon className="w-4 h-4" /> E-STOP
            </button>
          </div>
        </div>

        {/* Right: Telemetry HUD & Multi-modal Status (5 Cols) */}
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
                <p className="text-base font-bold text-emerald-400 mt-0.5">
                  {pose.linear_speed.toFixed(2)} m/s
                </p>
              </div>

              <div className="p-2.5 bg-slate-900/70 rounded-lg border border-slate-800">
                <span className="text-[10px] text-slate-400 uppercase">Active Primitive</span>
                <p className="text-base font-bold text-white mt-0.5">
                  {simulationState?.active_command || 'STOP'}
                </p>
              </div>
            </div>
          </div>

          {/* Multi-modal Pipeline Alignment */}
          <div className="p-4 bg-slate-800/60 border border-slate-700/80 rounded-xl space-y-3">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" /> Multi-modal Evidence Link
            </h3>

            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800 font-mono">
                <span className="text-slate-400">Voice Recognized:</span>
                <span className="font-semibold text-slate-200">
                  {simulationState?.voice_command || 'None'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800 font-mono">
                <span className="text-slate-400">Joystick Vector:</span>
                <span className="font-semibold text-slate-200">
                  {simulationState?.joystick_direction || 'Neutral'}
                </span>
              </div>

              <div className="flex items-center justify-between p-2 rounded bg-slate-900/60 border border-slate-800 font-mono">
                <span className="text-slate-400">Command Reliability (CRS):</span>
                <span
                  className={`font-bold ${
                    (simulationState?.crs ?? 0) >= 85
                      ? 'text-emerald-400'
                      : (simulationState?.crs ?? 0) >= 50
                      ? 'text-amber-400'
                      : 'text-rose-400'
                  }`}
                >
                  {simulationState?.crs !== undefined && simulationState?.crs !== null
                    ? `${simulationState.crs.toFixed(1)} / 100`
                    : 'N/A'}
                </span>
              </div>
            </div>

            {simulationState?.last_rejected_command && (
              <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/60 text-xs font-mono text-rose-300">
                <div className="flex items-center gap-1.5 font-bold mb-1">
                  <XCircle className="w-3.5 h-3.5" />
                  Rejected: {simulationState.last_rejected_command}
                </div>
                <p className="text-[11px] text-rose-400/90">
                  {simulationState.last_rejection_reason}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Command Execution Audit Log Table */}
      <div className="border border-slate-800 rounded-xl overflow-hidden bg-slate-950/50">
        <div className="px-4 py-3 bg-slate-800/50 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-2">
            <Crosshair className="w-4 h-4 text-cyan-400" />
            Command Execution Audit Trail (Gateway Verified)
          </h3>
          <span className="text-xs text-slate-500 font-mono">
            {executionLogs.length} events logged
          </span>
        </div>

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
                <th className="px-3 py-2">Coordinates (Pre → Post)</th>
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
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getBadgeStyle(
                            log.authorization_state
                          )}`}
                        >
                          {log.authorization_state}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold border flex items-center gap-1 w-fit ${getResultBadgeStyle(
                            log.execution_result
                          )}`}
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
                        ({log.pose_before.x.toFixed(1)}, {log.pose_before.y.toFixed(1)}) → (
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
      </div>
    </div>
  );
};

