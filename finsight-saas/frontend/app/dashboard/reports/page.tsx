"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { getReports, type ReportSummary, type PaginatedReports } from "@/lib/api";


export default function ReportsPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filterCompany, setFilterCompany] = useState("");
  const [filterForecast, setFilterForecast] = useState("");

  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    getReports(page)
      .then((data: PaginatedReports) => {
        setReports(data.items);
        setTotalPages(data.total_pages);
        setTotal(data.total);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page, user]);

  const FORECAST_STYLES: Record<string, string> = {
    buy: "text-green-400 bg-green-400/10 border border-green-400/30",
    hold: "text-yellow-400 bg-yellow-400/10 border border-yellow-400/30",
    sell: "text-red-400 bg-red-400/10 border border-red-400/30",
  };

  const SENTIMENT_STYLES: Record<string, string> = {
    bullish: "text-green-400",
    bearish: "text-red-400",
    neutral: "text-slate-400",
  };

  return (
    <div className="min-h-screen bg-[#0a0a12] text-white p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8 flex items-center gap-4">
          <button
            onClick={() => router.back()}
            className="text-slate-400 hover:text-white transition text-sm"
          >
            ← Back
          </button>
          <div>
            <h1 className="text-2xl font-black">Report History</h1>
            <p className="text-slate-400 text-sm mt-0.5">{total} total analyses</p>
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-4 mb-6 flex-wrap">
          <input
            id="filter-company"
            type="text"
            placeholder="Filter by company..."
            value={filterCompany}
            onChange={(e) => { setFilterCompany(e.target.value); setPage(1); }}
            className="bg-white/6 border border-white/12 rounded-xl px-4 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/40 w-64"
          />
          <select
            id="filter-forecast"
            value={filterForecast}
            onChange={(e) => { setFilterForecast(e.target.value); setPage(1); }}
            className="bg-white/6 border border-white/12 rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-violet-500/40"
          >
            <option value="">All forecasts</option>
            <option value="buy">Buy</option>
            <option value="hold">Hold</option>
            <option value="sell">Sell</option>
          </select>
        </div>

        {/* Table */}
        <div className="overflow-hidden rounded-2xl border border-white/10 bg-white/3">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
            </div>
          ) : reports.length === 0 ? (
            <div className="text-center py-16 text-slate-500">
              <p className="text-4xl mb-3">📭</p>
              <p>No reports found</p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/8 bg-white/4">
                  {["Company", "Question", "Risk Score", "Sentiment", "Forecast", "Status", "Date"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {reports.map((r) => (
                  <tr key={r.id} className="hover:bg-white/3 transition-colors">
                    <td className="px-4 py-4 font-semibold text-white">{r.company}</td>
                    <td className="px-4 py-4 text-slate-400 text-sm max-w-xs">
                      <span className="truncate block max-w-[200px]">{r.user_query}</span>
                    </td>
                    <td className="px-4 py-4">
                      {r.risk_score !== null ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${Math.round((r.risk_score ?? 0) * 100)}%`,
                                background: (r.risk_score ?? 0) > 0.7 ? "#ef4444" : (r.risk_score ?? 0) > 0.4 ? "#f59e0b" : "#22c55e",
                              }}
                            />
                          </div>
                          <span className="text-xs text-slate-300 tabular-nums">
                            {Math.round((r.risk_score ?? 0) * 100)}
                          </span>
                        </div>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-4">
                      <span className={`text-xs font-semibold capitalize ${SENTIMENT_STYLES[r.sentiment ?? ""] ?? "text-slate-400"}`}>
                        {r.sentiment ?? "—"}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      {r.forecast ? (
                        <span className={`text-xs font-bold uppercase px-2 py-1 rounded-full ${FORECAST_STYLES[r.forecast] ?? ""}`}>
                          {r.forecast}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-4">
                      <span className={`text-xs px-2 py-1 rounded-full ${
                        r.status === "complete"
                          ? "text-green-400 bg-green-400/10"
                          : r.status === "failed"
                          ? "text-red-400 bg-red-400/10"
                          : "text-yellow-400 bg-yellow-400/10"
                      }`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-4 text-slate-500 text-xs">
                      {new Date(r.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 mt-6">
            <button
              id="prev-page"
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page === 1}
              className="px-4 py-2 rounded-xl text-sm text-slate-400 hover:text-white border border-white/10 hover:border-white/20 disabled:opacity-40 transition"
            >
              ← Previous
            </button>
            <span className="text-sm text-slate-400">
              Page {page} of {totalPages}
            </span>
            <button
              id="next-page"
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page === totalPages}
              className="px-4 py-2 rounded-xl text-sm text-slate-400 hover:text-white border border-white/10 hover:border-white/20 disabled:opacity-40 transition"
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
