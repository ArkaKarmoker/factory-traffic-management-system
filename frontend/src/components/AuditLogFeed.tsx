"use client";

import React, { useState } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AuditLogItem } from "@/lib/api";
import { History, ChevronDown, ChevronUp, Code2, Copy, Check } from "lucide-react";

interface AuditLogFeedProps {
  logs: AuditLogItem[];
}

export function AuditLogFeed({ logs }: AuditLogFeedProps) {
  const [expandedIds, setExpandedIds] = useState<Record<number, boolean>>({});
  const [copiedId, setCopiedId] = useState<number | null>(null);

  const toggleExpand = (id: number) => {
    setExpandedIds((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleCopy = (id: number, details: unknown, e?: React.MouseEvent) => {
    if (e) {
      e.stopPropagation();
    }
    navigator.clipboard.writeText(JSON.stringify(details, null, 2));
    setCopiedId(id);
    setTimeout(() => {
      setCopiedId((curr) => (curr === id ? null : curr));
    }, 2000);
  };

  const getBadgeForEvent = (eventType: string) => {
    if (eventType.includes("EMERGENCY")) {
      return <Badge variant="emergency" className="text-[9px] sm:text-[10px] break-all sm:break-normal">{eventType}</Badge>;
    }
    if (eventType.includes("MANUAL")) {
      return <Badge variant="warning" className="text-[9px] sm:text-[10px] break-all sm:break-normal">{eventType}</Badge>;
    }
    if (eventType.includes("OFFLINE") || eventType.includes("VIOLATION")) {
      return <Badge variant="destructive" className="text-[9px] sm:text-[10px] break-all sm:break-normal">{eventType}</Badge>;
    }
    if (eventType.includes("SIGNAL_CHANGED") || eventType.includes("ACK")) {
      return <Badge variant="success" className="text-[9px] sm:text-[10px] break-all sm:break-normal">{eventType}</Badge>;
    }
    return <Badge variant="secondary" className="text-[9px] sm:text-[10px] break-all sm:break-normal">{eventType}</Badge>;
  };

  return (
    <Card className="border-slate-800 bg-slate-900/90 shadow-xl">
      <CardHeader className="p-4 sm:p-6 pb-2 sm:pb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 sm:w-5 sm:h-5 text-purple-400" />
            <CardTitle className="text-sm sm:text-base text-white">Live System Audit Trail</CardTitle>
          </div>
          <Badge variant="outline" className="text-[10px] sm:text-xs font-mono text-slate-400">
            {logs.length} Events Tracked
          </Badge>
        </div>
        <CardDescription className="text-xs">
          Immutable timeline of all state transitions, preemption triggers, sensor ingestions, and hardware ACKs.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-4 sm:p-6 pt-0 sm:pt-0">
        {logs.length === 0 ? (
          <div className="text-center py-8 text-xs text-slate-500">
            No audit logs captured yet. Send vehicle events or manual commands to populate.
          </div>
        ) : (
          <div className="overflow-y-auto overflow-x-hidden max-h-[380px] divide-y divide-slate-800/60 pr-1">
            {logs.map((log) => {
              const timeStr = new Date(log.timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              });
              const hasDetails = log.details && Object.keys(log.details).length > 0;
              const isExpanded = !!expandedIds[log.id];
              const isCopied = copiedId === log.id;

              return (
                <div key={log.id} className="py-2 sm:py-2.5 flex flex-col gap-1 text-xs min-w-0 transition-colors">
                  <div className="flex items-start justify-between gap-2 min-w-0">
                    <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap min-w-0 flex-1">
                      <span className="font-mono text-slate-400 text-[10px] sm:text-[11px] shrink-0">{timeStr}</span>
                      {getBadgeForEvent(log.event_type)}
                      {log.direction && (
                        <span className="font-bold text-slate-300 text-[10px] sm:text-[11px]">[{log.direction}]</span>
                      )}
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      {log.command_id && (
                        <span className="font-mono text-[9px] sm:text-[10px] text-slate-500 hidden sm:inline">
                          {log.command_id}
                        </span>
                      )}
                      {hasDetails && (
                        <button
                          type="button"
                          onClick={() => toggleExpand(log.id)}
                          className="flex items-center gap-1 text-[9px] sm:text-[10px] font-mono px-1.5 sm:px-2 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/60"
                          title={isExpanded ? "Collapse JSON payload" : "Expand full JSON payload"}
                        >
                          <Code2 className="w-3 h-3 text-cyan-400" />
                          <span>{isExpanded ? "Hide JSON" : "Details"}</span>
                          {isExpanded ? (
                            <ChevronUp className="w-3 h-3 text-slate-400" />
                          ) : (
                            <ChevronDown className="w-3 h-3 text-slate-400" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {hasDetails && (
                    <>
                      {!isExpanded ? (
                        <div className="flex items-center justify-between gap-1.5 sm:gap-2 text-[10px] sm:text-[11px] font-mono min-w-0">
                          <button
                            type="button"
                            onClick={() => toggleExpand(log.id)}
                            className="truncate flex-1 text-left text-slate-400 hover:text-slate-200 px-1.5 py-0.5 rounded hover:bg-slate-800/50 transition-colors"
                            title="Click to view full JSON payload"
                          >
                            {JSON.stringify(log.details)}
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleCopy(log.id, log.details, e)}
                            className="px-1.5 py-0.5 rounded border border-slate-700/50 hover:border-slate-600 bg-slate-800/40 hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors shrink-0 flex items-center gap-1 text-[10px]"
                            title="Copy JSON payload"
                          >
                            {isCopied ? (
                              <>
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                                <span className="text-emerald-400 font-sans text-[10px]">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-3.5 h-3.5 text-slate-400 hover:text-slate-200" />
                                <span className="font-sans text-[10px]">Copy</span>
                              </>
                            )}
                          </button>
                        </div>
                      ) : (
                        <div className="mt-1 p-2.5 rounded-md bg-slate-950/90 border border-slate-800/80 font-mono text-[11px] text-slate-300 shadow-inner">
                          <div className="flex items-center justify-between mb-1.5 pb-1 border-b border-slate-800/60 text-[10px] text-slate-400">
                            <span className="font-semibold text-cyan-400 flex items-center gap-1.5">
                              <Code2 className="w-3 h-3" />
                              Payload JSON Details
                            </span>
                            <div className="flex items-center gap-2">
                              <span className="text-slate-500">{Object.keys(log.details).length} fields</span>
                              <button
                                type="button"
                                onClick={(e) => handleCopy(log.id, log.details, e)}
                                className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors border border-slate-700/50"
                                title="Copy JSON payload"
                              >
                                {isCopied ? (
                                  <>
                                    <Check className="w-3 h-3 text-emerald-400" />
                                    <span className="text-emerald-400 text-[10px]">Copied</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3 h-3" />
                                    <span className="text-[10px]">Copy</span>
                                  </>
                                )}
                              </button>
                            </div>
                          </div>
                          <pre className="whitespace-pre-wrap break-all text-emerald-400/90 font-mono text-[11px] leading-relaxed">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
