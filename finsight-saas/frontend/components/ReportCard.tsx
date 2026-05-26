"use client";

import { useState } from "react";
import { RiskGauge } from "./RiskGauge";
import { SentimentBadge } from "./SentimentBadge";
import type { ReportData } from "../lib/api";

interface ReportCardProps {
  report: ReportData;
  compact?: boolean;
}

const FORECAST_CONFIG = {
  buy: { label: "BUY", color: "#22c55e", bg: "rgba(34, 197, 94, 0.12)", icon: "📈" },
  hold: { label: "HOLD", color: "#f59e0b", bg: "rgba(245, 158, 11, 0.12)", icon: "⏸" },
  sell: { label: "SELL", color: "#ef4444", bg: "rgba(239, 68, 68, 0.12)", icon: "📉" },
};

export function ReportCard({ report, compact = false }: ReportCardProps) {
  const [expanded, setExpanded] = useState(false);

  const forecast = report.forecast
    ? FORECAST_CONFIG[report.forecast as keyof typeof FORECAST_CONFIG]
    : null;

  return (
    <div className="group relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-slate-900 to-slate-800 shadow-xl transition-all duration-300 hover:border-white/20 hover:shadow-2xl">
      {/* Gradient accent top bar */}
      <div className="h-1 w-full bg-gradient-to-r from-violet-500 via-blue-500 to-cyan-500" />

      <div className="p-6 space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-xl font-bold text-white">{report.company}</h3>
            <p className="text-sm text-slate-400 mt-1 line-clamp-2">{report.user_query}</p>
          </div>

          {/* Forecast badge */}
          {forecast && (
            <div
              className="flex-shrink-0 ml-4 flex flex-col items-center rounded-xl px-4 py-2"
              style={{ background: forecast.bg, border: `1px solid ${forecast.color}33` }}
            >
              <span className="text-2xl">{forecast.icon}</span>
              <span
                className="text-xs font-black tracking-widest mt-1"
                style={{ color: forecast.color }}
              >
                {forecast.label}
              </span>
            </div>
          )}
        </div>

        {/* Metrics row */}
        <div className="flex flex-wrap items-center gap-4">
          {/* Risk gauge */}
          {report.risk_score !== null && (
            <div className="flex-shrink-0">
              <RiskGauge score={report.risk_score} size={140} />
            </div>
          )}

          {/* Sentiment + summary */}
          <div className="flex-1 min-w-0 space-y-3">
            <SentimentBadge
              sentiment={report.sentiment as "bullish" | "bearish" | "neutral" | null}
              confidence={report.sentiment_confidence}
              size="lg"
            />

            {report.risk_summary && (
              <div className="rounded-lg bg-white/5 p-3 border border-white/8">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">
                  Risk Analysis
                </p>
                <p className="text-sm text-slate-300">{report.risk_summary}</p>
              </div>
            )}
          </div>
        </div>

        {/* Forecast rationale */}
        {report.forecast_rationale && (
          <div className="rounded-lg bg-white/5 p-3 border border-white/8">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-1">
              Forecast Rationale
            </p>
            <p className="text-sm text-slate-300">{report.forecast_rationale}</p>
          </div>
        )}

        {/* Full report toggle */}
        {report.decision_report && !compact && (
          <div>
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs font-semibold text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-1"
            >
              {expanded ? "▲ Hide Full Report" : "▼ View Full Report"}
            </button>

            {expanded && (
              <div className="mt-3 rounded-xl bg-black/40 border border-white/10 p-5 overflow-auto max-h-96">
                <div
                  className="prose prose-sm prose-invert max-w-none text-slate-300"
                  dangerouslySetInnerHTML={{
                    __html: report.decision_report
                      .replace(/^## (.+)/gm, '<h2 class="text-white font-bold text-lg mt-4 mb-2">$1</h2>')
                      .replace(/^### (.+)/gm, '<h3 class="text-slate-200 font-semibold mt-3 mb-1">$1</h3>')
                      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
                      .replace(/\n/g, "<br/>"),
                  }}
                />
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        {report.completed_at && (
          <p className="text-xs text-slate-500">
            Generated {new Date(report.completed_at).toLocaleString()}
          </p>
        )}

        {/* Error state */}
        {report.error && (
          <div className="rounded-lg bg-red-950/50 border border-red-500/30 p-3">
            <p className="text-xs text-red-400">⚠ {report.error}</p>
          </div>
        )}
      </div>
    </div>
  );
}
