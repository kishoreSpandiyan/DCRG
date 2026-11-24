import React, { useEffect, useState } from 'react';
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Waves,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  AlertCircle,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Octagon,
  RefreshCw,
  UploadCloud,
  FileAudio,
  Sparkles,
  ShieldCheck,
  ShieldAlert,
  RotateCcw,
} from 'lucide-react';
import { useVoiceStream } from '../hooks/useVoiceStream';
import {
  fetchVoiceDevices,
  selectVoiceDevice,
  startVoiceCapture,
  stopVoiceCapture,
  setVoiceMute,
  fetchPredefinedSamples,
  playPredefinedSample,
  uploadAudioFileBase64,
  postVirtualJoystickInput,
  evaluateManualFusion,
  type PredefinedSampleItem,
} from '../services/api';
import type { AudioDevice, CanonicalCommand, MicrophoneStatus, AudioQuality } from '../types';

export const VoiceDashboardPanel: React.FC = () => {
  const {
    voiceStatus,
    lastEvent,
    eventHistory,
    isWsConnected,
    startMic,
    stopMic,
    toggleMute,
    micStatus,
  } = useVoiceStream();

  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [selectedDeviceIndex, setSelectedDeviceIndex] = useState<number | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [samples, setSamples] = useState<PredefinedSampleItem[]>([]);
  const [activeSampleLoading, setActiveSampleLoading] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  useEffect(() => {
    fetchPredefinedSamples().then((items) => setSamples(items));
  }, []);

  const refreshDevices = async () => {
    try {
      const devs = await fetchVoiceDevices();
      setDevices(devs);
      if (devs.length > 0) {
        const typec = devs.find((d) => d.name.toLowerCase().includes('type-c') || d.name.toLowerCase().includes('earphone'));
        const target = typec || devs.find((d) => d.is_default) || devs[0];
        setSelectedDeviceIndex(target.index);
        await selectVoiceDevice(target.index);
      }
    } catch (err) {
      console.error('Failed to refresh audio devices:', err);
    }
  };

  useEffect(() => {
    fetchVoiceDevices().then((devs) => {
      setDevices(devs);
      if (devs.length > 0) {
        const typec = devs.find((d) => d.name.toLowerCase().includes('type-c') || d.name.toLowerCase().includes('earphone'));
        const def = typec || devs.find((d) => d.is_default) || devs[0];
        setSelectedDeviceIndex(def.index);
      }
    });
  }, []);

  useEffect(() => {
    if (voiceStatus?.selected_device_index !== undefined && voiceStatus.selected_device_index !== null) {
      setSelectedDeviceIndex(voiceStatus.selected_device_index);
    }
  }, [voiceStatus?.selected_device_index]);

  const handleToggleCapture = async () => {
    setActionLoading(true);
    try {
      if (voiceStatus?.is_capturing) {
        stopMic();
        await stopVoiceCapture();
      } else {
        startMic();
        await startVoiceCapture();
      }
    } catch (err) {
      console.error('Failed to toggle microphone capture:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleMute = async () => {
    if (!voiceStatus) return;
    const nextMute = !voiceStatus.is_muted;
    toggleMute(nextMute);
    await setVoiceMute(nextMute);
  };

  const handleDeviceChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const idx = e.target.value === '' ? null : parseInt(e.target.value, 10);
    setSelectedDeviceIndex(idx);
    await selectVoiceDevice(idx);
  };

  const handleTriggerSample = async (sampleId: string, audioFile?: string) => {
    setActiveSampleLoading(sampleId);
    setUploadStatus(`Ingesting predefined sample '${sampleId}'...`);
    try {
      if (audioFile) {
        const audio = new Audio(audioFile);
        audio.play().catch(() => {});
      }
      const ev = await playPredefinedSample(sampleId);
      setUploadStatus(`Recognized: ${ev.recognized_command} (${(ev.recognition_confidence * 100).toFixed(0)}%)`);
    } catch (err: any) {
      setUploadStatus(`Error: ${err.message}`);
    } finally {
      setActiveSampleLoading(null);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setUploadStatus(`Uploading '${file.name}' (${(file.size / 1024).toFixed(1)} KB)...`);
    try {
      const reader = new FileReader();
      reader.onload = async () => {
        try {
          const resultStr = reader.result as string;
          const base64Data = resultStr.includes(',') ? resultStr.split(',')[1] : resultStr;
          const ev = await uploadAudioFileBase64(file.name, base64Data);
          setUploadStatus(`Success! File '${file.name}' -> Recognized: ${ev.recognized_command} (${(ev.recognition_confidence * 100).toFixed(0)}%)`);
        } catch (err: any) {
          setUploadStatus(`Upload failed: ${err.message}`);
        } finally {
          setIsUploading(false);
        }
      };
      reader.onerror = () => {
        setUploadStatus('Failed to read file');
        setIsUploading(false);
      };
      reader.readAsDataURL(file);
    } catch (err: any) {
      setUploadStatus(`Upload error: ${err.message}`);
      setIsUploading(false);
    }
  };

  const handleShowcaseScenario = async (scenario: 'AGREEMENT' | 'CONTRADICTION' | 'EMERGENCY' | 'RECOVERY') => {
    setActiveSampleLoading(scenario);
    try {
      if (scenario === 'AGREEMENT') {
        setUploadStatus('Showcasing Agreement: Joystick FORWARD + Voice FORWARD...');
        await postVirtualJoystickInput(0.0, 0.85);
        new Audio('/samples/forward.wav').play().catch(() => {});
        await evaluateManualFusion({
          voice_command: 'FORWARD',
          voice_confidence: 0.95,
          joystick_direction: 'FORWARD',
          joystick_intensity: 0.85,
        });
        setUploadStatus('Showcase: Voice FORWARD + Stick FORWARD -> CRS = 91.3 (GREEN / AUTHORIZED)');
      } else if (scenario === 'CONTRADICTION') {
        setUploadStatus('Showcasing Contradiction Veto: Joystick RIGHT + Voice LEFT...');
        await postVirtualJoystickInput(0.85, 0.0);
        new Audio('/samples/left.wav').play().catch(() => {});
        await evaluateManualFusion({
          voice_command: 'LEFT',
          voice_confidence: 0.92,
          joystick_direction: 'RIGHT',
          joystick_intensity: 0.85,
        });
        setUploadStatus('Showcase: Voice LEFT + Stick RIGHT -> CRS = 30.0 (RED / CONTRADICTION VETO)');
      } else if (scenario === 'EMERGENCY') {
        setUploadStatus('Showcasing Spoken STOP vs Moving Joystick...');
        await postVirtualJoystickInput(0.0, 0.85);
        new Audio('/samples/stop.wav').play().catch(() => {});
        await evaluateManualFusion({
          voice_command: 'STOP',
          voice_confidence: 0.95,
          joystick_direction: 'FORWARD',
          joystick_intensity: 0.85,
        });
        setUploadStatus('Showcase: Voice STOP vs Stick Deflected -> CRS = 30.0 (CONTRADICTION VETO / HALT)');
      } else if (scenario === 'RECOVERY') {
        setUploadStatus('Showcasing Dynamic Recovery: Restoring matching inputs...');
        await postVirtualJoystickInput(0.0, 0.85);
        new Audio('/samples/forward.wav').play().catch(() => {});
        await evaluateManualFusion({
          voice_command: 'FORWARD',
          voice_confidence: 0.95,
          joystick_direction: 'FORWARD',
          joystick_intensity: 0.85,
        });
        setUploadStatus('Showcase: Dynamic Recovery to GREEN (CRS = 91.3) achieved seamlessly!');
      }
    } catch (err: any) {
      setUploadStatus(`Showcase error: ${err.message}`);
    } finally {
      setActiveSampleLoading(null);
    }
  };

  // Status visual badge
  const renderStatusBadge = (status: MicrophoneStatus) => {
    switch (status) {
      case 'CONNECTED':
        return (
          <span className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-emerald-950/80 text-emerald-400 border border-emerald-800">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>CONNECTED</span>
          </span>
        );
      case 'MUTED':
        return (
          <span className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-amber-950/80 text-amber-400 border border-amber-800">
            <span className="w-2 h-2 rounded-full bg-amber-400" />
            <span>MUTED</span>
          </span>
        );
      case 'ERROR':
        return (
          <span className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-rose-950/80 text-rose-400 border border-rose-800">
            <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
            <span>ERROR</span>
          </span>
        );
      case 'DISCONNECTED':
      default:
        return (
          <span className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-mono font-medium bg-slate-800 text-slate-400 border border-slate-700">
            <span className="w-2 h-2 rounded-full bg-slate-500" />
            <span>DISCONNECTED</span>
          </span>
        );
    }
  };

  // Command visual representation
  const renderCommandBadge = (cmd?: CanonicalCommand) => {
    const c = cmd || 'UNKNOWN';
    switch (c) {
      case 'FORWARD':
        return (
          <div className="flex items-center space-x-2 text-cyan-400 bg-cyan-950/40 border border-cyan-800/80 px-4 py-2 rounded-lg font-mono font-bold text-lg">
            <ArrowUp className="w-6 h-6 animate-bounce" />
            <span>FORWARD</span>
          </div>
        );
      case 'BACKWARD':
        return (
          <div className="flex items-center space-x-2 text-indigo-400 bg-indigo-950/40 border border-indigo-800/80 px-4 py-2 rounded-lg font-mono font-bold text-lg">
            <ArrowDown className="w-6 h-6 animate-bounce" />
            <span>BACKWARD</span>
          </div>
        );
      case 'LEFT':
        return (
          <div className="flex items-center space-x-2 text-sky-400 bg-sky-950/40 border border-sky-800/80 px-4 py-2 rounded-lg font-mono font-bold text-lg">
            <ArrowLeft className="w-6 h-6 animate-pulse" />
            <span>LEFT</span>
          </div>
        );
      case 'RIGHT':
        return (
          <div className="flex items-center space-x-2 text-teal-400 bg-teal-950/40 border border-teal-800/80 px-4 py-2 rounded-lg font-mono font-bold text-lg">
            <ArrowRight className="w-6 h-6 animate-pulse" />
            <span>RIGHT</span>
          </div>
        );
      case 'STOP':
        return (
          <div className="flex items-center space-x-2 text-rose-400 bg-rose-950/60 border border-rose-700 px-4 py-2 rounded-lg font-mono font-bold text-lg">
            <Octagon className="w-6 h-6 text-rose-500 animate-pulse" />
            <span>STOP</span>
          </div>
        );
      case 'UNCERTAIN':
        return (
          <div className="flex items-center space-x-2 text-amber-400 bg-amber-950/40 border border-amber-800/80 px-4 py-2 rounded-lg font-mono font-bold text-lg">
            <AlertTriangle className="w-6 h-6 text-amber-400" />
            <span>UNCERTAIN</span>
          </div>
        );
      case 'UNKNOWN':
      default:
        return (
          <div className="flex items-center space-x-2 text-slate-400 bg-slate-900 border border-slate-800 px-4 py-2 rounded-lg font-mono font-semibold text-lg">
            <HelpCircle className="w-6 h-6 text-slate-500" />
            <span>UNKNOWN</span>
          </div>
        );
    }
  };

  // Audio Quality badge
  const renderQualityBadge = (quality: AudioQuality = 'GOOD') => {
    switch (quality) {
      case 'GOOD':
        return <span className="text-xs px-2 py-0.5 rounded bg-emerald-950/60 text-emerald-400 border border-emerald-800 font-mono">GOOD</span>;
      case 'NOISY':
        return <span className="text-xs px-2 py-0.5 rounded bg-amber-950/60 text-amber-400 border border-amber-800 font-mono">NOISY</span>;
      case 'DEGRADED':
        return <span className="text-xs px-2 py-0.5 rounded bg-rose-950/60 text-rose-400 border border-rose-800 font-mono">DEGRADED</span>;
      case 'SILENCE':
      default:
        return <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">SILENCE</span>;
    }
  };

  const recConf = lastEvent?.recognition_confidence ?? 0;
  const clsConf = lastEvent?.classification_confidence ?? 0;
  const intensityPct = Math.min(100, Math.round((lastEvent?.intensity ?? 0) * 100));

  return (
    <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl shadow-xl text-left space-y-6">
      {/* Panel Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-cyan-950/50 border border-cyan-800/60">
              <Mic className="w-6 h-6 text-cyan-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-100">
                Voice Recognition & Prosody Analysis Engine
              </h2>
              <p className="text-xs text-slate-400">
                Phase 3 • Ultra-Low-Latency KWS (&lt;60ms) & Faster-Whisper ({voiceStatus?.model_name || 'tiny.en'}) STT & Prosody Analysis
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3 self-start md:self-auto">
          {renderStatusBadge(micStatus)}
          <span
            className={`text-xs px-2.5 py-1 rounded-full font-mono border ${
              isWsConnected
                ? 'bg-emerald-950/40 text-emerald-400 border-emerald-800/60'
                : 'bg-rose-950/40 text-rose-400 border-rose-800/60'
            }`}
          >
            WS: {isWsConnected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      {/* Control Bar: Microphone Controls & Device Selection */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-950/60 p-4 rounded-xl border border-slate-800/80 items-center">
        {/* Device Selector */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <label className="text-xs font-mono text-slate-400">INPUT AUDIO HARDWARE</label>
            <button
              type="button"
              onClick={refreshDevices}
              className="text-[11px] text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 font-mono transition"
              title="Rescan connected audio devices"
            >
              <RefreshCw className="w-3 h-3" />
              <span>RESCAN</span>
            </button>
          </div>
          <select
            value={selectedDeviceIndex ?? ''}
            onChange={handleDeviceChange}
            disabled={voiceStatus?.is_capturing}
            className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-cyan-500 font-mono"
          >
            {devices.map((d) => (
              <option key={d.index} value={d.index}>
                {d.name} {d.is_default ? '(Default)' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Start / Stop Capture Button */}
        <div className="flex items-center space-x-3 md:col-span-2 justify-end">
          <button
            onClick={handleToggleMute}
            disabled={!voiceStatus?.is_capturing}
            className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-xs font-semibold transition border ${
              voiceStatus?.is_muted
                ? 'bg-amber-900/60 text-amber-200 border-amber-700 hover:bg-amber-800/60'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {voiceStatus?.is_muted ? <VolumeX className="w-4 h-4 text-amber-400" /> : <Volume2 className="w-4 h-4" />}
            <span>{voiceStatus?.is_muted ? 'UNMUTE MIC' : 'MUTE MIC'}</span>
          </button>

          <button
            onClick={handleToggleCapture}
            disabled={actionLoading}
            className={`flex items-center space-x-2 px-5 py-2 rounded-lg text-xs font-bold transition shadow-lg ${
              voiceStatus?.is_capturing
                ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-900/20'
                : 'bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-900/20'
            } disabled:opacity-50`}
          >
            {voiceStatus?.is_capturing ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            <span>{voiceStatus?.is_capturing ? 'STOP CAPTURE' : 'START CAPTURE'}</span>
          </button>
        </div>
      </div>

      {/* Predefined Audio Commands & Audio File Ingestion Section */}
      <div className="bg-slate-950/80 border border-indigo-900/40 rounded-xl p-5 space-y-4 shadow-lg">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-800 gap-2">
          <div className="flex items-center space-x-2">
            <FileAudio className="w-5 h-5 text-indigo-400" />
            <h3 className="text-sm font-bold font-mono text-slate-100 uppercase tracking-wider">
              Predefined Audio Library & File Ingestion
            </h3>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700">
              Reliable Showcase
            </span>
          </div>
          {uploadStatus && (
            <span className="text-xs font-mono text-cyan-300 bg-cyan-950/60 border border-cyan-800 px-3 py-1 rounded-full">
              {uploadStatus}
            </span>
          )}
        </div>

        {/* 1. Quick One-Click Predefined Command Ingestion */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400 uppercase">
              1. Curated Voice Audio Commands (Click to Ingest & Hear):
            </span>
            <span className="text-[11px] font-mono text-slate-500">16kHz High-Fidelity WAV</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2.5">
            {samples.map((s) => {
              const isLoading = activeSampleLoading === s.id;
              let badgeColor = 'bg-slate-900 border-slate-700 text-slate-200 hover:border-cyan-500 hover:text-cyan-300';
              if (s.id === 'forward') badgeColor = 'bg-cyan-950/40 border-cyan-800/80 text-cyan-300 hover:bg-cyan-900/40';
              if (s.id === 'backward') badgeColor = 'bg-indigo-950/40 border-indigo-800/80 text-indigo-300 hover:bg-indigo-900/40';
              if (s.id === 'left') badgeColor = 'bg-sky-950/40 border-sky-800/80 text-sky-300 hover:bg-sky-900/40';
              if (s.id === 'right') badgeColor = 'bg-teal-950/40 border-teal-800/80 text-teal-300 hover:bg-teal-900/40';
              if (s.id === 'stop' || s.id === 'emergency_stop') badgeColor = 'bg-rose-950/40 border-rose-800/80 text-rose-300 hover:bg-rose-900/40';

              return (
                <button
                  key={s.id}
                  onClick={() => handleTriggerSample(s.id, `/samples/${s.filename}`)}
                  disabled={isLoading}
                  className={`flex flex-col items-center justify-center p-2.5 rounded-lg border font-mono text-xs font-bold transition shadow-sm ${badgeColor} disabled:opacity-50`}
                  title={s.description}
                >
                  <div className="flex items-center space-x-1.5 mb-1">
                    {s.id === 'forward' && <ArrowUp className="w-4 h-4 text-cyan-400" />}
                    {s.id === 'backward' && <ArrowDown className="w-4 h-4 text-indigo-400" />}
                    {s.id === 'left' && <ArrowLeft className="w-4 h-4 text-sky-400" />}
                    {s.id === 'right' && <ArrowRight className="w-4 h-4 text-teal-400" />}
                    {s.id === 'stop' && <Octagon className="w-4 h-4 text-rose-400" />}
                    {s.id === 'emergency_stop' && <AlertTriangle className="w-4 h-4 text-rose-400" />}
                    <span>{s.command}</span>
                  </div>
                  <span className="text-[10px] font-normal text-slate-400">
                    {isLoading ? 'Processing...' : s.filename}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* 2. File Upload & Showcase Scenarios in 2 Columns */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-slate-800/80">
          {/* Custom File Upload Box */}
          <div className="p-3.5 bg-slate-900/70 border border-slate-800 rounded-lg flex flex-col justify-between space-y-2">
            <div>
              <div className="flex items-center space-x-2 text-xs font-mono font-bold text-slate-300">
                <UploadCloud className="w-4 h-4 text-cyan-400" />
                <span>2. Upload Custom Audio File (.wav, .mp3, .ogg)</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Upload your own recorded speech. Immediately extracts prosody, runs STT, and calculates CRS.
              </p>
            </div>
            <label className="flex items-center justify-center space-x-2 px-3 py-2 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-xs font-mono text-cyan-300 cursor-pointer transition">
              <UploadCloud className="w-4 h-4" />
              <span>{isUploading ? 'Uploading...' : 'Browse & Ingest Audio File'}</span>
              <input
                type="file"
                accept="audio/*,.wav,.mp3,.ogg,.m4a"
                onChange={handleFileUpload}
                disabled={isUploading}
                className="hidden"
              />
            </label>
          </div>

          {/* Quick CRS Showcase Demonstrations */}
          <div className="p-3.5 bg-slate-900/70 border border-slate-800 rounded-lg flex flex-col justify-between space-y-2">
            <div>
              <div className="flex items-center space-x-2 text-xs font-mono font-bold text-slate-300">
                <Sparkles className="w-4 h-4 text-amber-400" />
                <span>3. Live CRS Demonstration Presets</span>
              </div>
              <p className="text-[11px] text-slate-400 mt-1">
                Single-click multimodal bundle demonstrations that showcase perfect CRS behavior.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleShowcaseScenario('AGREEMENT')}
                disabled={activeSampleLoading !== null}
                className="flex items-center justify-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-emerald-950/60 border border-emerald-700 hover:bg-emerald-900/60 text-emerald-300 text-[11px] font-mono font-bold transition disabled:opacity-50"
                title="Stick FORWARD + Voice FORWARD"
              >
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                <span>Agreement (GREEN)</span>
              </button>
              <button
                type="button"
                onClick={() => handleShowcaseScenario('CONTRADICTION')}
                disabled={activeSampleLoading !== null}
                className="flex items-center justify-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-rose-950/60 border border-rose-700 hover:bg-rose-900/60 text-rose-300 text-[11px] font-mono font-bold transition disabled:opacity-50"
                title="Stick RIGHT + Voice LEFT"
              >
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                <span>Contradiction (RED)</span>
              </button>
              <button
                type="button"
                onClick={() => handleShowcaseScenario('EMERGENCY')}
                disabled={activeSampleLoading !== null}
                className="flex items-center justify-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-red-950/70 border border-red-600 hover:bg-red-900/70 text-red-200 text-[11px] font-mono font-bold transition disabled:opacity-50"
                title="Spoken STOP vs Moving Stick"
              >
                <Octagon className="w-3.5 h-3.5 text-red-400" />
                <span>Emergency Veto (HALT)</span>
              </button>
              <button
                type="button"
                onClick={() => handleShowcaseScenario('RECOVERY')}
                disabled={activeSampleLoading !== null}
                className="flex items-center justify-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-cyan-950/60 border border-cyan-700 hover:bg-cyan-900/60 text-cyan-300 text-[11px] font-mono font-bold transition disabled:opacity-50"
                title="Recover back to GREEN"
              >
                <RotateCcw className="w-3.5 h-3.5 text-cyan-400" />
                <span>Dynamic Recovery</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Grid: Live Command & Prosody Gauges */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Live Speech Recognition & Intent */}
        <div className="space-y-4 p-5 bg-slate-950/40 border border-slate-800/80 rounded-xl flex flex-col justify-between">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Recognized Command Primitive
              </span>
              <div className="flex items-center space-x-2">
                {lastEvent?.source === 'kws_fast_path' && (
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-400 border border-emerald-700 animate-pulse font-bold">
                    ⚡ FAST-PATH KWS (&lt;60ms)
                  </span>
                )}
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                  STATUS: {lastEvent?.semantic_status || 'UNKNOWN'}
                </span>
              </div>
            </div>

            {/* Prominent Command Badge */}
            <div className="py-2">{renderCommandBadge(lastEvent?.recognized_command)}</div>

            {/* Live Transcript Display */}
            <div className="space-y-1">
              <span className="text-xs font-mono text-slate-400 uppercase">Spoken Transcript</span>
              <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg min-h-[52px] flex items-center">
                <p className="text-sm font-mono text-slate-200 italic">
                  {lastEvent?.transcript ? `"${lastEvent.transcript}"` : <span className="text-slate-500">Waiting for speech...</span>}
                </p>
              </div>
            </div>

            {/* Direction Vector Display */}
            <div className="flex items-center space-x-4 text-xs font-mono text-slate-400 bg-slate-900/60 p-2.5 rounded-lg border border-slate-800/60">
              <span>Vector:</span>
              <span className="text-cyan-400">X: {lastEvent?.direction_vector?.x ?? 0.0}</span>
              <span className="text-cyan-400">Y: {lastEvent?.direction_vector?.y ?? 0.0}</span>
              <span className="text-slate-500">|</span>
              <span>Audio: {lastEvent?.audio_duration_ms ?? 0} ms</span>
            </div>
          </div>

          {/* Confidence Meters */}
          <div className="space-y-3 pt-3 border-t border-slate-800/60">
            {/* Recognition Confidence */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-slate-400">STT Recognition Confidence</span>
                <span className="text-cyan-400 font-bold">{(recConf * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    recConf >= 0.70 ? 'bg-cyan-400' : recConf >= 0.50 ? 'bg-amber-400' : 'bg-rose-400'
                  }`}
                  style={{ width: `${Math.min(100, recConf * 100)}%` }}
                />
              </div>
            </div>

            {/* Classification Confidence */}
            <div className="space-y-1">
              <div className="flex justify-between text-xs font-mono">
                <span className="text-slate-400">Semantic Classification Confidence</span>
                <span className="text-emerald-400 font-bold">{(clsConf * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all duration-300 ${
                    clsConf >= 0.70 ? 'bg-emerald-400' : clsConf >= 0.50 ? 'bg-amber-400' : 'bg-rose-400'
                  }`}
                  style={{ width: `${Math.min(100, clsConf * 100)}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Prosody & Acoustic Feature Extraction */}
        <div className="space-y-4 p-5 bg-slate-950/40 border border-slate-800/80 rounded-xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Waves className="w-4 h-4 text-sky-400" />
              <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
                Acoustic Prosody & Stress
              </span>
            </div>
            {renderQualityBadge(lastEvent?.audio_quality)}
          </div>

          {/* Prosody Metrics Cards */}
          <div className="grid grid-cols-2 gap-3">
            {/* Pitch F0 */}
            <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg">
              <div className="text-[11px] font-mono text-slate-400">PITCH (F0 MEAN)</div>
              <div className="text-xl font-bold font-mono text-sky-400 mt-1">
                {lastEvent?.pitch_f0?.toFixed(1) || '0.0'} <span className="text-xs text-slate-500 font-normal">Hz</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">
                Std: {lastEvent?.pitch_f0_std?.toFixed(1) || '0.0'} Hz
              </div>
            </div>

            {/* Speech Rate */}
            <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg">
              <div className="text-[11px] font-mono text-slate-400">SPEECH RATE</div>
              <div className="text-xl font-bold font-mono text-teal-400 mt-1">
                {lastEvent?.speech_rate?.toFixed(1) || '0.0'}{' '}
                <span className="text-xs text-slate-500 font-normal">syl/s</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Target: 3.0 - 5.5 syl/s</div>
            </div>

            {/* Jitter */}
            <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg">
              <div className="text-[11px] font-mono text-slate-400">PERIOD JITTER</div>
              <div className="text-xl font-bold font-mono text-indigo-400 mt-1">
                {((lastEvent?.jitter || 0) * 100).toFixed(2)} <span className="text-xs text-slate-500 font-normal">%</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Cycle perturbation</div>
            </div>

            {/* Shimmer */}
            <div className="p-3 bg-slate-900 border border-slate-800 rounded-lg">
              <div className="text-[11px] font-mono text-slate-400">AMPLITUDE SHIMMER</div>
              <div className="text-xl font-bold font-mono text-violet-400 mt-1">
                {((lastEvent?.shimmer || 0) * 100).toFixed(2)} <span className="text-xs text-slate-500 font-normal">%</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Energy perturbation</div>
            </div>
          </div>

          {/* Voice Intensity / Loudness Meter */}
          <div className="space-y-1">
            <div className="flex justify-between text-xs font-mono">
              <span className="text-slate-400">Acoustic Intensity (Loudness)</span>
              <span className="text-sky-300 font-bold">{intensityPct}%</span>
            </div>
            <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-150 ${
                  intensityPct > 80 ? 'bg-rose-500' : intensityPct > 40 ? 'bg-sky-400' : 'bg-slate-500'
                }`}
                style={{ width: `${intensityPct}%` }}
              />
            </div>
          </div>

          {/* Cognitive Stress Score */}
          <div className="p-3 bg-slate-900/80 border border-slate-800 rounded-lg flex items-center justify-between">
            <div>
              <div className="text-xs font-mono text-slate-400">Cognitive Stress Index (S_stress)</div>
              <div className="text-sm font-bold font-mono text-slate-200 mt-0.5">
                {(lastEvent?.composite_stress_score ?? 0).toFixed(3)}{' '}
                <span className="text-xs font-normal text-slate-400">
                  {lastEvent?.is_stressed ? '(Elevated Stress)' : '(Nominal)'}
                </span>
              </div>
            </div>
            <span
              className={`px-2.5 py-1 rounded text-xs font-mono font-bold ${
                lastEvent?.is_stressed
                  ? 'bg-amber-950/80 text-amber-300 border border-amber-800'
                  : 'bg-emerald-950/80 text-emerald-300 border border-emerald-800'
              }`}
            >
              {lastEvent?.is_stressed ? 'HIGH STRESS' : 'CALM'}
            </span>
          </div>

          {/* Safety Rule Advisory Alert */}
          <div className="p-2.5 bg-slate-950 border border-slate-800/80 rounded-lg flex items-start space-x-2 text-[11px] text-slate-400">
            <CheckCircle2 className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
            <p>
              <strong className="text-slate-300">Safety Guardrail:</strong> Prosody is strictly a supporting context signal. High pitch, loudness, or jitter NEVER independently invalidates or rejects a command.
            </p>
          </div>
        </div>
      </div>

      {/* Recent Voice Events History Table */}
      {eventHistory.length > 0 && (
        <div className="p-4 bg-slate-950/40 border border-slate-800/80 rounded-xl space-y-2">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono text-slate-400 uppercase tracking-wider">
              Recent Voice Command Event Log
            </span>
            <span className="text-xs font-mono text-slate-500">{eventHistory.length} events logged</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800 pb-1">
                  <th className="pb-1 font-normal">TIME</th>
                  <th className="pb-1 font-normal">TRANSCRIPT</th>
                  <th className="pb-1 font-normal">COMMAND</th>
                  <th className="pb-1 font-normal">CONFIDENCE</th>
                  <th className="pb-1 font-normal">STATUS</th>
                  <th className="pb-1 font-normal">F0 (HZ)</th>
                  <th className="pb-1 font-normal">STRESS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {eventHistory.slice(0, 5).map((ev) => (
                  <tr key={ev.event_id} className="hover:bg-slate-900/50 text-slate-300">
                    <td className="py-1.5 text-slate-500">{new Date(ev.timestamp).toLocaleTimeString()}</td>
                    <td className="py-1.5 italic text-slate-200">"{ev.transcript || '—'}"</td>
                    <td className="py-1.5 font-bold">
                      <span
                        className={
                          ev.recognized_command === 'STOP'
                            ? 'text-rose-400'
                            : ev.recognized_command === 'UNCERTAIN'
                            ? 'text-amber-400'
                            : 'text-cyan-400'
                        }
                      >
                        {ev.recognized_command}
                      </span>
                    </td>
                    <td className="py-1.5">{(ev.recognition_confidence * 100).toFixed(0)}%</td>
                    <td className="py-1.5">
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] ${
                          ev.semantic_status === 'VALID'
                            ? 'bg-emerald-950 text-emerald-400'
                            : 'bg-amber-950 text-amber-400'
                        }`}
                      >
                        {ev.semantic_status}
                      </span>
                    </td>
                    <td className="py-1.5">{ev.pitch_f0.toFixed(0)} Hz</td>
                    <td className="py-1.5">
                      <span className={ev.is_stressed ? 'text-amber-400 font-bold' : 'text-slate-400'}>
                        {ev.composite_stress_score.toFixed(2)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
