"use client";

import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  Car,
  Truck,
  Forklift,
  Siren,
  CheckCircle2,
  XCircle,
  Copy,
  Server,
  Play,
  RotateCcw,
  Sparkles,
  WifiOff,
  Wifi,
} from "lucide-react";

interface SimulatorPanelProps {
  onActionComplete: () => void;
  controllerStatus?: string;
}

export function SimulatorPanel({ onActionComplete, controllerStatus }: SimulatorPanelProps) {
  const [activeTab, setActiveTab] = useState<"vehicles" | "emergency" | "controller" | "helpers">("vehicles");

  // Vehicle form state
  const [direction, setDirection] = useState("NORTH");
  const [vehicleType, setVehicleType] = useState("FORKLIFT");
  const [vehicleId, setVehicleId] = useState("VH-FL-501");
  const [lastEventId, setLastEventId] = useState("");
  const [loading, setLoading] = useState(false);

  // Ingest Arrival
  const handleVehicleArrive = async (isDuplicate = false) => {
    try {
      setLoading(true);
      const eventId = isDuplicate && lastEventId ? lastEventId : `evt-${Date.now().toString().slice(-6)}`;
      if (!isDuplicate) setLastEventId(eventId);

      const res = await api.postSensorEvent({
        event_id: eventId,
        junction_id: "A",
        direction,
        event_type: "VEHICLE_ARRIVED",
        vehicle_id: vehicleId,
        vehicle_type: vehicleType,
        sequence_no: Math.floor(Math.random() * 9000) + 1000,
      });

      if (res.status === "DUPLICATE_IGNORED") {
        toast.info(`Idempotency Verified! Duplicate ${eventId} safely ignored without increasing queue.`);
      } else if (res.status === "DUPLICATE_VEHICLE_IGNORED") {
        toast.warning(`Duplicate Vehicle! Vehicle ${vehicleId} is already waiting in the queue.`);
      } else {
        toast.success(`Vehicle ${vehicleId} arrived at ${direction} [Queue updated].`);
        // Auto-advance vehicle ID for seamless multi-vehicle testing (e.g. VH-FL-501 -> VH-FL-502)
        const match = vehicleId.match(/^(.*?)(\d+)$/);
        if (match) {
          const prefix = match[1];
          const num = parseInt(match[2], 10) + 1;
          setVehicleId(`${prefix}${num}`);
        }
      }
      onActionComplete();
    } catch (err: any) {
      toast.error(`Sensor error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Ingest Clearance
  const handleVehicleCleared = async () => {
    try {
      setLoading(true);
      const eventId = `evt-clr-${Date.now().toString().slice(-6)}`;
      await api.postSensorEvent({
        event_id: eventId,
        junction_id: "A",
        direction,
        event_type: "VEHICLE_CLEARED",
        vehicle_id: vehicleId,
      });
      toast.success(`Vehicle ${vehicleId} cleared from ${direction} queue.`);
      onActionComplete();
    } catch (err: any) {
      toast.error(`Sensor clearance error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Emergency Preemption Quick Fire
  const handleEmergencyTrigger = async (targetDir: string) => {
    try {
      setLoading(true);
      const eventId = `evt-em-${Date.now().toString().slice(-6)}`;
      await api.postSensorEvent({
        event_id: eventId,
        junction_id: "A",
        direction: targetDir,
        event_type: "VEHICLE_ARRIVED",
        vehicle_id: `AMB-${Math.floor(Math.random() * 900) + 100}`,
        vehicle_type: "EMERGENCY",
      });
      toast.warning(`EMERGENCY SIREN on ${targetDir}! Safe preemption sequence initiated.`);
      onActionComplete();
    } catch (err: any) {
      toast.error(`Emergency error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Controller Offline / Online Toggle
  const handleToggleControllerStatus = async (statusToSet: "OFFLINE" | "ONLINE") => {
    try {
      setLoading(true);
      await api.postControllerEvent({
        junction_id: "A",
        status: statusToSet,
        device_type: "SIGNAL_CONTROLLER",
      });
      toast.info(`Controller simulated: ${statusToSet}`);
      onActionComplete();
    } catch (err: any) {
      toast.error(`Controller simulation error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Step Tick
  const handleStepTick = async () => {
    try {
      setLoading(true);
      const res: any = await api.postTick("A");
      const stepName =
        res?.transition_step === "YELLOW_CLEARING"
          ? "YELLOW Clearance (5s)"
          : res?.transition_step === "ALL_RED_CLEARING"
          ? "ALL-RED Clearance (2s)"
          : `STEADY (${res?.phase || "GREEN"})`;
      toast.success(`Advanced State Machine: ${stepName}`);
      onActionComplete();
    } catch (err: any) {
      toast.error(`Tick error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Reset demo
  const handleReset = async () => {
    try {
      setLoading(true);
      await api.postReset("A");
      toast.success("Junction A reset to clean initial state.");
      onActionComplete();
    } catch (err: any) {
      toast.error(`Reset error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card className="border-slate-800 bg-slate-900/90 shadow-xl">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <CardTitle className="text-base text-white">Evaluator Test Simulator</CardTitle>
          </div>
          <Badge variant="outline" className="text-xs text-indigo-400 border-indigo-900/80 bg-indigo-950/30">
            Interactive Testbed
          </Badge>
        </div>
        <CardDescription>
          Simulate road sensors, vehicle arrivals, emergency preemption, and controller telemetry without hardware.
        </CardDescription>

        {/* Tab switcher buttons with clean responsive scroll */}
        <div className="flex items-center gap-1.5 pt-2 border-b border-slate-800/80 pb-2 overflow-x-auto no-scrollbar">
          <button
            onClick={() => setActiveTab("vehicles")}
            className={`px-2.5 sm:px-3 py-1.5 rounded-md text-[11px] sm:text-xs font-medium whitespace-nowrap shrink-0 transition ${
              activeTab === "vehicles" ? "bg-blue-600 text-white shadow-sm" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            Vehicles & Queues
          </button>
          <button
            onClick={() => setActiveTab("emergency")}
            className={`px-2.5 sm:px-3 py-1.5 rounded-md text-[11px] sm:text-xs font-medium whitespace-nowrap shrink-0 transition ${
              activeTab === "emergency" ? "bg-rose-600 text-white shadow-sm font-semibold" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            Emergency Siren
          </button>
          <button
            onClick={() => setActiveTab("controller")}
            className={`px-2.5 sm:px-3 py-1.5 rounded-md text-[11px] sm:text-xs font-medium whitespace-nowrap shrink-0 transition ${
              activeTab === "controller" ? "bg-amber-600 text-slate-950 font-bold shadow-sm" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            Controller Hardware
          </button>
          <button
            onClick={() => setActiveTab("helpers")}
            className={`px-2.5 sm:px-3 py-1.5 rounded-md text-[11px] sm:text-xs font-medium whitespace-nowrap shrink-0 transition ${
              activeTab === "helpers" ? "bg-slate-700 text-white shadow-sm" : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
            }`}
          >
            Step & Reset
          </button>
        </div>
      </CardHeader>

      <CardContent className="pt-3">
        {/* TAB 1: VEHICLES & QUEUES */}
        {activeTab === "vehicles" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* Direction Select */}
              <div>
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Direction
                </label>
                <Select value={direction} onValueChange={(val) => setDirection(val)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select Direction" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="NORTH">NORTH</SelectItem>
                    <SelectItem value="SOUTH">SOUTH</SelectItem>
                    <SelectItem value="EAST">EAST</SelectItem>
                    <SelectItem value="WEST">WEST</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Vehicle Type Select */}
              <div>
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Vehicle Type
                </label>
                <Select value={vehicleType} onValueChange={(val) => setVehicleType(val)}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select Vehicle Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="FORKLIFT">FORKLIFT (Priority 15)</SelectItem>
                    <SelectItem value="TRUCK">TRUCK (Priority 25)</SelectItem>
                    <SelectItem value="EMPLOYEE_VEHICLE">EMPLOYEE CAR (Priority 5)</SelectItem>
                    <SelectItem value="EMERGENCY">EMERGENCY (Dominant)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Vehicle ID input */}
              <div>
                <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1">
                  Vehicle Identifier
                </label>
                <input
                  type="text"
                  value={vehicleId}
                  onChange={(e) => setVehicleId(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                />
              </div>
            </div>

            {/* Action buttons (2-Column Grid on both Mobile and Desktop) */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <Button
                variant="default"
                disabled={loading}
                onClick={() => handleVehicleArrive(false)}
                className="text-xs gap-1.5 h-10 font-semibold bg-blue-600 hover:bg-blue-500 text-white shadow-sm"
              >
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-300 shrink-0" />
                <span className="hidden sm:inline">Simulate Arrival (+ Queue)</span>
                <span className="sm:hidden">Arrive (+Queue)</span>
              </Button>

              <Button
                variant="outline"
                disabled={loading}
                onClick={handleVehicleCleared}
                className="text-xs gap-1.5 h-10 font-semibold bg-rose-950/40 hover:bg-rose-900/50 text-rose-200 border border-rose-800/80 shadow-sm"
              >
                <XCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                <span className="hidden sm:inline">Simulate Cleared (- Queue)</span>
                <span className="sm:hidden">Cleared (-Queue)</span>
              </Button>
            </div>

            {lastEventId && (
              <Button
                variant="secondary"
                size="sm"
                disabled={loading}
                onClick={() => handleVehicleArrive(true)}
                className="w-full text-xs gap-1.5 bg-purple-950/60 text-purple-300 border border-purple-800 hover:bg-purple-900/60 h-9 font-mono"
                title="Resends identical event_id to prove idempotency"
              >
                <Copy className="w-3.5 h-3.5 shrink-0" />
                <span className="hidden sm:inline">Test Idempotency Guard (Resend {lastEventId})</span>
                <span className="sm:hidden">Resend Duplicate ({lastEventId})</span>
              </Button>
            )}
          </div>
        )}

        {/* TAB 2: EMERGENCY PREEMPTION */}
        {activeTab === "emergency" && (
          <div className="space-y-4">
            <p className="text-xs text-slate-300 leading-relaxed bg-rose-950/30 p-2.5 rounded-lg border border-rose-900/40">
              <strong className="text-rose-400">Section 7 Test:</strong> Spawns an emergency vehicle approaching a direction. The system immediately initiates the mandatory safe sequence: GREEN → YELLOW (5s) → ALL-RED → EMERGENCY GREEN.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {["EAST", "WEST", "NORTH", "SOUTH"].map((dir) => (
                <Button
                  key={dir}
                  variant="emergency"
                  size="sm"
                  disabled={loading}
                  onClick={() => handleEmergencyTrigger(dir)}
                  className="text-xs gap-2 h-10 w-full justify-center"
                >
                  <Siren className="w-4 h-4 shrink-0" />
                  <span>Ambulance on <strong>{dir}</strong></span>
                </Button>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: CONTROLLER HARDWARE */}
        {activeTab === "controller" && (
          <div className="space-y-4">
            <p className="text-xs text-slate-300 leading-relaxed bg-amber-950/30 p-2.5 rounded-lg border border-amber-900/40">
              <strong className="text-amber-400">Section 9 Test:</strong> Simulates physical hardware failures. If the controller reports OFFLINE, the junction immediately enters fail-safe DEGRADED mode with ALL-RED caution.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <Button
                variant="destructive"
                size="sm"
                disabled={loading || controllerStatus === "OFFLINE"}
                onClick={() => handleToggleControllerStatus("OFFLINE")}
                className="text-xs gap-2 h-10 font-semibold"
              >
                <WifiOff className="w-4 h-4 shrink-0" />
                Simulate Controller OFFLINE
              </Button>

              <Button
                variant="success"
                size="sm"
                disabled={loading || controllerStatus === "ONLINE"}
                onClick={() => handleToggleControllerStatus("ONLINE")}
                className="text-xs gap-2 h-10 font-semibold"
              >
                <Wifi className="w-4 h-4 shrink-0" />
                Simulate Controller ONLINE (ACK)
              </Button>
            </div>
          </div>
        )}

        {/* TAB 4: STEP & RESET */}
        {activeTab === "helpers" && (
          <div className="space-y-4">
            <p className="text-xs text-slate-300 leading-relaxed bg-slate-950 p-2.5 rounded-lg border border-slate-800">
              Fast-forward state machine transitions without waiting real-world seconds, or reset Junction A back to its initial seeded state.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <Button
                variant="outline"
                size="sm"
                disabled={loading}
                onClick={handleStepTick}
                className="text-xs gap-2 h-10 text-blue-400 border-blue-900 bg-blue-950/30 hover:bg-blue-950/60 font-semibold"
              >
                <Play className="w-4 h-4 shrink-0" />
                Advance Transition Step (Tick)
              </Button>

              <Button
                variant="secondary"
                size="sm"
                disabled={loading}
                onClick={handleReset}
                className="text-xs gap-2 h-10 text-slate-300 hover:text-white"
              >
                <RotateCcw className="w-4 h-4 shrink-0 text-slate-400" />
                Reset Demo to Clean State
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
