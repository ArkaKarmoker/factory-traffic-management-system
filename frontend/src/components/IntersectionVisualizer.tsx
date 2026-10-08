"use client";

import React from "react";
import { JunctionStatus } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import {
  Truck,
  Car,
  Siren,
  ShieldAlert,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";

interface IntersectionVisualizerProps {
  status: JunctionStatus | null;
}

// Helper to render traffic light head
function TrafficLightHead({
  state,
  desiredState,
  direction,
}: {
  state?: "RED" | "YELLOW" | "GREEN";
  desiredState?: "RED" | "YELLOW" | "GREEN";
  direction: string;
}) {
  const isRed = state === "RED";
  const isYellow = state === "YELLOW";
  const isGreen = state === "GREEN";

  const hasMismatch = state && desiredState && state !== desiredState;

  return (
    <div className="flex flex-col items-center gap-0.5 sm:gap-1 bg-slate-950 p-1.5 sm:p-2 rounded-lg sm:rounded-xl border border-slate-700 shadow-2xl">
      <div className="text-[9px] sm:text-[10px] font-bold text-slate-400 tracking-wider mb-0.5">{direction}</div>
      <div className="flex flex-col gap-1 sm:gap-1.5 p-0.5 sm:p-1 bg-slate-900 rounded-md sm:rounded-lg border border-slate-800">
        {/* Red Lens */}
        <div
          className={`w-3.5 h-3.5 sm:w-5 sm:h-5 rounded-full transition-all duration-300 ${
            isRed
              ? "bg-rose-500 signal-glow-red ring-2 ring-rose-400 ring-offset-1 ring-offset-slate-900"
              : "bg-rose-950/40 border border-rose-900/40"
          }`}
        />
        {/* Yellow Lens */}
        <div
          className={`w-3.5 h-3.5 sm:w-5 sm:h-5 rounded-full transition-all duration-300 ${
            isYellow
              ? "bg-amber-400 signal-glow-yellow ring-2 ring-amber-300 ring-offset-1 ring-offset-slate-900"
              : "bg-amber-950/40 border border-amber-900/40"
          }`}
        />
        {/* Green Lens */}
        <div
          className={`w-3.5 h-3.5 sm:w-5 sm:h-5 rounded-full transition-all duration-300 ${
            isGreen
              ? "bg-emerald-500 signal-glow-green ring-2 ring-emerald-400 ring-offset-1 ring-offset-slate-900"
              : "bg-emerald-950/40 border border-emerald-900/40"
          }`}
        />
      </div>

      {hasMismatch && (
        <span className="text-[8px] sm:text-[9px] text-amber-400 font-semibold mt-0.5">
          Want: {desiredState}
        </span>
      )}
    </div>
  );
}

export function IntersectionVisualizer({ status }: IntersectionVisualizerProps) {
  const actual = status?.actual_signals || {
    NORTH: "GREEN",
    SOUTH: "GREEN",
    EAST: "RED",
    WEST: "RED",
  };
  const desired = status?.desired_signals || actual;
  const queues = status?.queues || { NORTH: 0, SOUTH: 0, EAST: 0, WEST: 0 };

  const getTransitionBadge = () => {
    if (status?.transition_step === "YELLOW_CLEARING") {
      return (
        <Badge variant="warning" className="animate-pulse tracking-wide font-bold text-[9px] sm:text-xs px-1.5 sm:px-2.5 py-0.5">
          YELLOW (5s)
        </Badge>
      );
    }
    if (status?.transition_step === "ALL_RED_CLEARING") {
      return (
        <Badge variant="destructive" className="animate-pulse tracking-wide font-bold text-[9px] sm:text-xs px-1.5 sm:px-2.5 py-0.5">
          ALL-RED (2s)
        </Badge>
      );
    }
    return (
      <Badge variant="outline" className="border-slate-700 text-slate-300 font-mono text-[9px] sm:text-[11px] px-1.5 sm:px-2.5 py-0.5">
        STEADY: {status?.phase || "NORTH_SOUTH"}
      </Badge>
    );
  };

  return (
    <div className="relative w-full aspect-square bg-slate-950/90 rounded-2xl border border-slate-800 shadow-2xl p-2.5 sm:p-6 flex flex-col justify-between items-center overflow-hidden">
      {/* Background Asphalt Roads */}
      <div className="absolute inset-x-[36%] inset-y-0 bg-slate-900" />
      <div className="absolute inset-y-[36%] inset-x-0 bg-slate-900" />

      {/* Road Curbs (Borders around the 4 quadrant sidewalks, leaving the 4-way intersection open and seamless) */}
      <div className="absolute top-0 left-0 w-[36%] h-[36%] border-r border-b border-slate-800" />
      <div className="absolute top-0 right-0 w-[36%] h-[36%] border-l border-b border-slate-800" />
      <div className="absolute bottom-0 left-0 w-[36%] h-[36%] border-r border-t border-slate-800" />
      <div className="absolute bottom-0 right-0 w-[36%] h-[36%] border-l border-t border-slate-800" />

      {/* Road Center Dash Lines (North-South) */}
      <div className="absolute top-0 bottom-[64%] left-1/2 -translate-x-1/2 w-0.5 border-r border-dashed border-slate-600 z-0" />
      <div className="absolute top-[64%] bottom-0 left-1/2 -translate-x-1/2 w-0.5 border-r border-dashed border-slate-600 z-0" />

      {/* Road Center Dash Lines (East-West) */}
      <div className="absolute left-0 right-[64%] top-1/2 -translate-y-1/2 h-0.5 border-b border-dashed border-slate-600 z-0" />
      <div className="absolute left-[64%] right-0 top-1/2 -translate-y-1/2 h-0.5 border-b border-dashed border-slate-600 z-0" />

      {/* ================= NORTH APPROACH ================= */}
      <div className="z-10 flex flex-col items-center gap-1 sm:gap-1.5 w-full pt-0.5 sm:pt-1">
        <div className="flex items-center gap-1.5 sm:gap-2">
          <Badge variant="secondary" className="bg-slate-900 border-slate-700 text-[10px] sm:text-xs gap-1 font-mono px-1.5 sm:px-2.5 py-0.5">
            <ArrowDown className="w-3 h-3 text-blue-400" /> NORTH Queue: {queues.NORTH}
          </Badge>
          {status?.emergency_direction === "NORTH" && (
            <Badge variant="emergency" className="gap-1 animate-pulse text-[10px] sm:text-xs px-1.5 sm:px-2.5 py-0.5">
              <Siren className="w-3 h-3" /> AMBULANCE
            </Badge>
          )}
        </div>
        <TrafficLightHead
          direction="NORTH"
          state={actual.NORTH}
          desiredState={desired.NORTH}
        />
      </div>

      {/* ================= MIDDLE ROW (WEST, CENTER HUB, EAST) ================= */}
      <div className="z-10 w-full flex items-center justify-between px-1 sm:px-2">
        {/* WEST APPROACH */}
        <div className="flex flex-col items-start gap-1 sm:gap-1.5">
          <Badge variant="secondary" className="bg-slate-900 border-slate-700 text-[10px] sm:text-xs gap-1 font-mono px-1.5 sm:px-2.5 py-0.5">
            <ArrowRight className="w-3 h-3 text-blue-400" /> WEST Queue: {queues.WEST}
          </Badge>
          {status?.emergency_direction === "WEST" && (
            <Badge variant="emergency" className="gap-1 animate-pulse text-[10px] sm:text-xs px-1.5 sm:px-2.5 py-0.5">
              <Siren className="w-3 h-3" /> AMBULANCE
            </Badge>
          )}
          <TrafficLightHead
            direction="WEST"
            state={actual.WEST}
            desiredState={desired.WEST}
          />
        </div>

        {/* CENTER INTERSECTION HUB */}
        <div className="w-24 h-24 sm:w-36 sm:h-36 rounded-xl sm:rounded-2xl bg-slate-950/95 border-2 border-slate-700/80 shadow-inner flex flex-col items-center justify-center p-1 sm:p-2 text-center z-20">
          <div className="text-[8px] sm:text-[10px] text-slate-400 uppercase tracking-widest font-bold">
            Intersection A
          </div>

          <div className="my-1 sm:my-1.5">{getTransitionBadge()}</div>

          <div className="text-[8px] sm:text-[10px] text-slate-400 font-mono">
            {status?.mode === "EMERGENCY" ? (
              <span className="text-rose-400 font-bold flex items-center gap-1">
                <ShieldAlert className="w-3 h-3 animate-spin" /> Preemption
              </span>
            ) : status?.mode === "MANUAL" ? (
              <span className="text-amber-400 font-bold">Manual Hold</span>
            ) : (
              <span className="text-emerald-400 font-semibold">Adaptive FSM</span>
            )}
          </div>
        </div>

        {/* EAST APPROACH */}
        <div className="flex flex-col items-end gap-1 sm:gap-1.5">
          <Badge variant="secondary" className="bg-slate-900 border-slate-700 text-[10px] sm:text-xs gap-1 font-mono px-1.5 sm:px-2.5 py-0.5">
            <ArrowLeft className="w-3 h-3 text-blue-400" /> EAST Queue: {queues.EAST}
          </Badge>
          {status?.emergency_direction === "EAST" && (
            <Badge variant="emergency" className="gap-1 animate-pulse text-[10px] sm:text-xs px-1.5 sm:px-2.5 py-0.5">
              <Siren className="w-3 h-3" /> AMBULANCE
            </Badge>
          )}
          <TrafficLightHead
            direction="EAST"
            state={actual.EAST}
            desiredState={desired.EAST}
          />
        </div>
      </div>

      {/* ================= SOUTH APPROACH ================= */}
      <div className="z-10 flex flex-col items-center gap-1 sm:gap-1.5 w-full pb-0.5 sm:pb-1">
        <TrafficLightHead
          direction="SOUTH"
          state={actual.SOUTH}
          desiredState={desired.SOUTH}
        />
        <div className="flex items-center gap-1.5 sm:gap-2">
          <Badge variant="secondary" className="bg-slate-900 border-slate-700 text-[10px] sm:text-xs gap-1 font-mono px-1.5 sm:px-2.5 py-0.5">
            <ArrowUp className="w-3 h-3 text-blue-400" /> SOUTH Queue: {queues.SOUTH}
          </Badge>
          {status?.emergency_direction === "SOUTH" && (
            <Badge variant="emergency" className="gap-1 animate-pulse text-[10px] sm:text-xs px-1.5 sm:px-2.5 py-0.5">
              <Siren className="w-3 h-3" /> AMBULANCE
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}
