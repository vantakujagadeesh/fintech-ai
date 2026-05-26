"use client";

interface UsageBarProps {
  used: number;
  limit: number;
  plan: string;
}

const PLAN_COLORS: Record<string, string> = {
  free: "#94a3b8",
  starter: "#6366f1",
  pro: "#f59e0b",
};

export function UsageBar({ used, limit, plan }: UsageBarProps) {
  const isUnlimited = limit >= 999999;
  const percentage = isUnlimited ? 0 : Math.min(100, (used / limit) * 100);
  const remaining = isUnlimited ? "∞" : Math.max(0, limit - used);
  const color = PLAN_COLORS[plan] ?? "#6366f1";

  const barColor =
    percentage > 80 ? "#ef4444" : percentage > 60 ? "#f59e0b" : color;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="text-slate-400 font-medium">
          Daily Queries
          <span
            className="ml-2 text-xs font-bold uppercase px-2 py-0.5 rounded-full"
            style={{
              background: `${color}22`,
              color,
              border: `1px solid ${color}44`,
            }}
          >
            {plan}
          </span>
        </span>
        <span className="text-slate-300 tabular-nums font-semibold">
          {used}
          <span className="text-slate-500 font-normal">
            /{isUnlimited ? "∞" : limit}
          </span>
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 w-full bg-white/10 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: isUnlimited ? "100%" : `${percentage}%`,
            background: isUnlimited
              ? `linear-gradient(90deg, ${color}, #a78bfa)`
              : barColor,
            boxShadow: `0 0 8px ${barColor}66`,
          }}
        />
      </div>

      <p className="text-xs text-slate-500">
        {isUnlimited
          ? "Unlimited queries on Pro plan"
          : `${remaining} queries remaining today`}
      </p>
    </div>
  );
}
