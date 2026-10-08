"use client";

import React from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { JunctionStatus } from "@/lib/api";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  Radio,
  RefreshCw,
  Sliders,
  ShieldAlert,
  Server,
  Zap,
} from "lucide-react";

interface HeaderProps {
  status: JunctionStatus | null;
  loading: boolean;
  isPolling: boolean;
  onTogglePolling: () => void;
  onRefresh: () => void;
}

export function Header({
  status,
  loading,
  isPolling,
  onTogglePolling,
  onRefresh,
}: HeaderProps) {
  const handleToggleClick = () => {
    if (isPolling) {
      toast.info("Live telemetry sync paused.");
    } else {
      toast.success("Live telemetry sync resumed (1s polling active).");
    }
    onTogglePolling();
  };

  const handleRefreshClick = () => {
    toast.info("Refreshing junction telemetry & audit logs...");
    onRefresh();
  };
  const getModeBadge = (mode?: string) => {
    switch (mode) {
      case "EMERGENCY":
        return <Badge variant="emergency" className="h-7 px-3 text-xs tracking-wider uppercase font-bold flex items-center">EMERGENCY PREEMPTION</Badge>;
      case "MANUAL":
        return <Badge variant="warning" className="h-7 px-3 text-xs tracking-wider uppercase font-bold flex items-center">MANUAL OVERRIDE</Badge>;
      case "DEGRADED":
        return <Badge variant="destructive" className="h-7 px-3 text-xs tracking-wider uppercase font-bold flex items-center">DEGRADED / FAIL-SAFE</Badge>;
      default:
        return <Badge variant="success" className="h-7 px-3 text-xs tracking-wider uppercase font-semibold flex items-center">AUTOMATIC ENGINE</Badge>;
    }
  };

  const isOffline = status?.controller_status === "OFFLINE";
  const isOnline = status?.controller_status === "ONLINE";

  const getStatusDot = () => {
    if (isOffline) {
      return (
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-rose-400" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.8)]" />
        </span>
      );
    }
    if (isOnline) {
      return (
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-emerald-400" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
        </span>
      );
    }
    return (
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 bg-amber-400" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.8)]" />
      </span>
    );
  };

  return (
    <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-50">
      {/* Emergency Global Alert Banner */}
      {status?.emergency_active && (
        <div className="bg-rose-600 text-white px-4 py-1.5 text-xs font-bold flex items-center justify-center gap-2 animate-pulse tracking-wide shadow-lg">
          <ShieldAlert className="w-4 h-4" />
          CRITICAL: EMERGENCY VEHICLE DETECTED APPROACHING {status.emergency_direction} — AUTOMATIC TRANSITION TO CLEARANCE PREEMPTION IN PROGRESS
        </div>
      )}

      {/* Controller Offline Alert Banner */}
      {isOffline && (
        <div className="bg-amber-600 text-slate-950 px-4 py-1.5 text-xs font-bold flex items-center justify-center gap-2 tracking-wide shadow-lg">
          <AlertTriangle className="w-4 h-4" />
          WARNING: HARDWARE CONTROLLER OFFLINE — JUNCTION OPERATING IN FAIL-SAFE ALL-RED CAUTION
        </div>
      )}

      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-14 sm:h-16 flex items-center justify-between">
        {/* Brand & Junction Title */}
        <div className="flex items-center gap-2.5 sm:gap-3">
          <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
            <Radio className="w-4 h-4 sm:w-5 sm:h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <h1 className="text-sm sm:text-lg font-bold text-white tracking-tight">Factory Traffic Control</h1>
              <Badge variant="outline" className="text-[10px] sm:text-xs text-blue-400 border-blue-800/80 bg-blue-950/40">
                Junction A
              </Badge>
            </div>
            <p className="text-[11px] sm:text-xs text-slate-400 hidden sm:block">Garment Facility Internal Roadways Telemetry & Automation</p>
          </div>
        </div>

        {/* Operating Badges & Controls */}
        <div className="flex items-center gap-2 sm:gap-4">
          <div className="hidden md:flex items-center gap-2">
            {getModeBadge(status?.mode)}
            
            <Badge
              variant="outline"
              className={`h-7 px-3 text-xs flex items-center gap-2 font-medium transition-colors ${
                isOffline
                  ? "bg-rose-950/50 border-rose-800/80 text-rose-200"
                  : "bg-slate-900 border-slate-700/80 text-slate-200"
              }`}
            >
              {getStatusDot()}
              <Server className={`w-3.5 h-3.5 ${isOffline ? "text-rose-400" : "text-slate-400"}`} />
              <span>
                Controller:{" "}
                <strong className={isOffline ? "text-rose-300 font-bold" : "text-emerald-400 font-bold"}>
                  {status?.controller_status || "CONNECTING"}
                </strong>
              </span>
            </Badge>
          </div>

          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              onClick={handleToggleClick}
              className={`text-xs gap-1.5 h-8 px-2.5 sm:h-9 sm:px-3 ${isPolling ? "text-emerald-400 border-emerald-900 bg-emerald-950/30" : "text-slate-400"}`}
            >
              <Activity className={`w-3.5 h-3.5 ${isPolling ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">{isPolling ? "Live Sync (1s)" : "Paused"}</span>
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={handleRefreshClick}
              disabled={loading}
              className="text-xs gap-1.5 h-8 px-2.5 sm:h-9 sm:px-3"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              <span className="hidden sm:inline">Refresh</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Mobile Sub-Header Status Row (< md) */}
      <div className="md:hidden border-t border-slate-800/80 bg-slate-950/95 px-3 py-1.5 flex items-center justify-between gap-2 overflow-x-auto no-scrollbar">
        <div className="flex items-center gap-1.5">
          {getModeBadge(status?.mode)}
          <Badge
            variant="outline"
            className={`h-7 px-2 text-[11px] flex items-center gap-1.5 font-medium shrink-0 transition-colors ${
              isOffline
                ? "bg-rose-950/50 border-rose-800/80 text-rose-200"
                : "bg-slate-900 border-slate-700/80 text-slate-200"
            }`}
          >
            {getStatusDot()}
            <Server className={`w-3 h-3 ${isOffline ? "text-rose-400" : "text-slate-400"}`} />
            <span>
              Controller:{" "}
              <strong className={isOffline ? "text-rose-300 font-bold" : "text-emerald-400 font-bold"}>
                {status?.controller_status || "CONNECTING"}
              </strong>
            </span>
          </Badge>
        </div>
        <div className="text-[10px] text-slate-400 font-mono shrink-0 pr-1">
          {isPolling ? "1s sync" : "paused"}
        </div>
      </div>
    </header>
  );
}
