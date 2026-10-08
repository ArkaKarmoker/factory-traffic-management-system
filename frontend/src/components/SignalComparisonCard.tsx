"use client";

import React from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { JunctionStatus } from "@/lib/api";
import { CheckCircle2, AlertTriangle, Cpu, Radio } from "lucide-react";

interface SignalComparisonProps {
  status: JunctionStatus | null;
}

export function SignalComparisonCard({ status }: SignalComparisonProps) {
  const desired = status?.desired_signals || {};
  const actual = status?.actual_signals || {};
  const directions = ["NORTH", "SOUTH", "EAST", "WEST"];

  const getColorClass = (state?: string) => {
    switch (state) {
      case "GREEN":
        return "text-emerald-400 font-bold bg-emerald-950/40 border-emerald-800";
      case "YELLOW":
        return "text-amber-400 font-bold bg-amber-950/40 border-amber-800";
      case "RED":
        return "text-rose-400 font-bold bg-rose-950/40 border-rose-800";
      default:
        return "text-slate-400 border-slate-800";
    }
  };

  const hasMismatch = directions.some((d) => desired[d] && actual[d] && desired[d] !== actual[d]);

  return (
    <Card className="border-slate-800 bg-slate-900/90 shadow-xl">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Cpu className="w-5 h-5 text-emerald-400" />
            <CardTitle className="text-base text-white">Desired vs Confirmed Telemetry</CardTitle>
          </div>
          {hasMismatch ? (
            <Badge variant="warning" className="text-xs gap-1">
              <AlertTriangle className="w-3 h-3" /> Awaiting Controller ACK
            </Badge>
          ) : (
            <Badge variant="success" className="text-xs gap-1">
              <CheckCircle2 className="w-3 h-3" /> State Synchronized
            </Badge>
          )}
        </div>
        <CardDescription>
          Section 9 Safety Distinction: Backend requested state vs physical hardware ACK confirmed state.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="pb-2 font-semibold">Direction</th>
                <th className="pb-2 font-semibold">
                  <span className="sm:hidden">Desired</span>
                  <span className="hidden sm:inline">Desired State (Backend Intent)</span>
                </th>
                <th className="pb-2 font-semibold">
                  <span className="sm:hidden">Confirmed</span>
                  <span className="hidden sm:inline">Actual State (Hardware Confirmed)</span>
                </th>
                <th className="pb-2 font-semibold text-right">
                  <span className="sm:hidden">Integrity</span>
                  <span className="hidden sm:inline">Integrity Status</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {directions.map((dir) => {
                const des = desired[dir] || "RED";
                const act = actual[dir] || "RED";
                const isSynced = des === act;

                return (
                  <tr key={dir} className="hover:bg-slate-800/30">
                    <td className="py-2.5 font-bold text-slate-200">{dir}</td>
                    <td className="py-2.5">
                      <span className={`px-2 py-0.5 rounded border text-[11px] ${getColorClass(des)}`}>
                        {des}
                      </span>
                    </td>
                    <td className="py-2.5">
                      <span className={`px-2 py-0.5 rounded border text-[11px] ${getColorClass(act)}`}>
                        {act}
                      </span>
                    </td>
                    <td className="py-2.5 text-right font-mono">
                      {isSynced ? (
                        <span className="text-emerald-400 inline-flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5" /> ACK SYNC
                        </span>
                      ) : (
                        <span className="text-amber-400 inline-flex items-center gap-1 font-semibold">
                          <AlertTriangle className="w-3.5 h-3.5" /> TRANSITIONING
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
