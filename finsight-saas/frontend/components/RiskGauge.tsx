"use client";

import { RadialBarChart, RadialBar, PolarAngleAxis, ResponsiveContainer } from "recharts";

interface RiskGaugeProps {
  score: number; // 0.0 – 1.0
  size?: number;
}

function getColor(score: number): string {
  if (score > 0.7) return "#ef4444"; // red
  if (score > 0.4) return "#f59e0b"; // yellow
  return "#22c55e"; // green
}

function getRiskLabel(score: number): string {
  if (score > 0.7) return "HIGH RISK";
  if (score > 0.4) return "MEDIUM RISK";
  return "LOW RISK";
}

export function RiskGauge({ score, size = 200 }: RiskGaugeProps) {
  const percentage = Math.round(score * 100);
  const color = getColor(score);
  const label = getRiskLabel(score);

  const data = [{ value: percentage, fill: color }];

  return (
    <div className="relative flex flex-col items-center">
      <div style={{ width: size, height: size * 0.6 }} className="relative">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="100%"
            innerRadius="70%"
            outerRadius="100%"
            barSize={18}
            data={data}
            startAngle={180}
            endAngle={0}
          >
            <PolarAngleAxis
              type="number"
              domain={[0, 100]}
              angleAxisId={0}
              tick={false}
            />
            <RadialBar
              background={{ fill: "rgba(255,255,255,0.08)" }}
              dataKey="value"
              angleAxisId={0}
              cornerRadius={10}
            />
          </RadialBarChart>
        </ResponsiveContainer>

        {/* Center label */}
        <div
          className="absolute bottom-0 left-1/2 -translate-x-1/2 flex flex-col items-center pb-2"
        >
          <span
            className="text-3xl font-black tabular-nums"
            style={{ color }}
          >
            {percentage}
          </span>
          <span className="text-[10px] font-semibold tracking-widest uppercase opacity-70">
            / 100
          </span>
        </div>
      </div>

      <div
        className="mt-2 px-3 py-1 rounded-full text-xs font-bold tracking-widest uppercase"
        style={{
          background: `${color}22`,
          color,
          border: `1px solid ${color}44`,
        }}
      >
        {label}
      </div>
    </div>
  );
}
