"use client";

interface SentimentBadgeProps {
  sentiment: "bullish" | "bearish" | "neutral" | null;
  confidence?: number | null;
  size?: "sm" | "md" | "lg";
}

const SENTIMENT_CONFIG = {
  bullish: {
    icon: "↑",
    label: "Bullish",
    bg: "rgba(34, 197, 94, 0.15)",
    border: "rgba(34, 197, 94, 0.4)",
    text: "#22c55e",
    glow: "0 0 12px rgba(34, 197, 94, 0.3)",
  },
  bearish: {
    icon: "↓",
    label: "Bearish",
    bg: "rgba(239, 68, 68, 0.15)",
    border: "rgba(239, 68, 68, 0.4)",
    text: "#ef4444",
    glow: "0 0 12px rgba(239, 68, 68, 0.3)",
  },
  neutral: {
    icon: "→",
    label: "Neutral",
    bg: "rgba(148, 163, 184, 0.15)",
    border: "rgba(148, 163, 184, 0.4)",
    text: "#94a3b8",
    glow: "0 0 12px rgba(148, 163, 184, 0.15)",
  },
};

const SIZE_CLASSES = {
  sm: "text-xs px-2 py-0.5 gap-1",
  md: "text-sm px-3 py-1 gap-1.5",
  lg: "text-base px-4 py-2 gap-2",
};

export function SentimentBadge({
  sentiment,
  confidence,
  size = "md",
}: SentimentBadgeProps) {
  if (!sentiment) {
    return (
      <span className="inline-flex items-center text-sm text-slate-500 px-3 py-1 rounded-full border border-slate-700 bg-slate-800/50">
        — Pending
      </span>
    );
  }

  const config = SENTIMENT_CONFIG[sentiment];
  const sizeClass = SIZE_CLASSES[size];

  return (
    <span
      className={`inline-flex items-center font-semibold rounded-full border ${sizeClass}`}
      style={{
        background: config.bg,
        borderColor: config.border,
        color: config.text,
        boxShadow: config.glow,
      }}
    >
      <span className="font-black text-base leading-none">{config.icon}</span>
      <span className="tracking-wide uppercase text-[11px] font-bold">
        {config.label}
      </span>
      {confidence !== null && confidence !== undefined && (
        <span
          className="ml-1 opacity-70 text-[10px]"
        >
          {Math.round(confidence * 100)}%
        </span>
      )}
    </span>
  );
}
