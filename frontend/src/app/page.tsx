"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import { Header } from "@/components/Header";
import { IntersectionVisualizer } from "@/components/IntersectionVisualizer";
import { SignalComparisonCard } from "@/components/SignalComparisonCard";
import { SimulatorPanel } from "@/components/SimulatorPanel";
import { ManualControls } from "@/components/ManualControls";
import { AuditLogFeed } from "@/components/AuditLogFeed";
import { Footer } from "@/components/Footer";
import { api, JunctionStatus, AuditLogItem } from "@/lib/api";
import { AlertCircle, Server } from "lucide-react";

export default function DashboardPage() {
  const [status, setStatus] = useState<JunctionStatus | null>(null);
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState<boolean>(true);

  const isPollingRef = useRef(isPolling);
  isPollingRef.current = isPolling;

  const fetchData = useCallback(async () => {
    try {
      const [statusData, historyData] = await Promise.all([
        api.getStatus("A"),
        api.getHistory("A", 40),
      ]);
      setStatus(statusData);
      setLogs(historyData);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to communicate with backend service.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Polling loop (1 second interval)
  useEffect(() => {
    fetchData();

    const interval = setInterval(() => {
      if (isPollingRef.current) {
        fetchData();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [fetchData]);

  const handleTogglePolling = () => {
    setIsPolling((prev) => !prev);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Navigation Header */}
      <Header
        status={status}
        loading={loading}
        isPolling={isPolling}
        onTogglePolling={handleTogglePolling}
        onRefresh={fetchData}
      />

      {/* Backend Disconnection Banner */}
      {error && (
        <div className="bg-amber-950/80 border-b border-amber-800 text-amber-200 px-4 py-3 text-xs flex items-center justify-center gap-2">
          <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>
            <strong>Backend Connection Notice:</strong> {error}. Ensure Django is running on port 8000:{" "}
            <code className="bg-slate-900 px-1.5 py-0.5 rounded font-mono text-amber-300">python manage.py runserver</code>
          </span>
        </div>
      )}

      {/* Main Content Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-6 lg:p-8 space-y-4 sm:space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 sm:gap-6 items-start">
          {/* Left Column: Visual Intersection & Signal Verification (7 cols) */}
          <div className="lg:col-span-7 space-y-4 sm:space-y-6">
            <IntersectionVisualizer status={status} />
            <SignalComparisonCard status={status} />
          </div>

          {/* Right Column: Interactive Simulator, Manual Controls & Audit Feed (5 cols) */}
          <div className="lg:col-span-5 space-y-4 sm:space-y-6">
            <SimulatorPanel
              onActionComplete={fetchData}
              controllerStatus={status?.controller_status}
            />
            <ManualControls
              currentMode={status?.mode}
              activeManualDirection={status?.manual_requested_direction}
              onActionComplete={fetchData}
            />
            <AuditLogFeed logs={logs} />
          </div>
        </div>
      </main>

      {/* Global Footer */}
      <Footer />
    </div>
  );
}
