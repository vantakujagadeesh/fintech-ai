const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("finsight_token");
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const tok = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(tok ? { Authorization: `Bearer ${tok}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail ?? "Request failed");
  }
  return res.json();
}

/* ── Types ── */
export interface AnalyzeRequest  { company: string; query: string; ingest_news?: boolean; }
export interface AnalyzeResponse { job_id: string; status: string; message: string; }
export interface ReportData {
  job_id: string; company: string; user_query: string;
  risk_score: number | null; risk_summary: string | null;
  sentiment: "bullish" | "bearish" | "neutral" | null;
  sentiment_confidence: number | null;
  forecast: "buy" | "hold" | "sell" | null;
  forecast_rationale: string | null;
  decision_report: string | null;
  error: string | null; completed_at: string | null;
}
export interface JobStatusResponse {
  job_id: string; status: string;
  report: ReportData | null; error: string | null;
}
export interface UsageResponse { used: number; limit: number; plan: string; date: string; remaining: number; }
export interface ReportSummary {
  id: string; job_id: string; company: string; user_query: string;
  risk_score: number | null; sentiment: string | null; forecast: string | null;
  status: string; created_at: string; completed_at: string | null;
}
export interface PaginatedReports {
  items: ReportSummary[]; total: number; page: number; page_size: number; total_pages: number;
}

/* ── API calls ── */
export const submitAnalysis   = (r: AnalyzeRequest)    => api<AnalyzeResponse>("/analyze", { method: "POST", body: JSON.stringify(r) });
export const getJobStatus     = (id: string)           => api<JobStatusResponse>(`/jobs/${id}/status`);
export const getUsage         = ()                     => api<UsageResponse>("/usage");
export const getReports       = (page = 1, ps = 20)    => api<PaginatedReports>(`/reports?page=${page}&page_size=${ps}`);
export const createCheckout = (plan: string, ok: string, cancel: string) =>
  api<{ checkout_url: string; session_id: string }>("/billing/create-checkout-session", {
    method: "POST", body: JSON.stringify({ plan, success_url: ok, cancel_url: cancel }),
  });

// Alias for backward compatibility
export const createCheckoutSession = (
  plan: "starter" | "pro",
  successUrl: string,
  cancelUrl: string
) => createCheckout(plan, successUrl, cancelUrl);

export const uploadPortfolio = async (file: File) => {
  const tok = getToken();
  const fd  = new FormData(); fd.append("file", file);
  const res = await fetch(`${API_BASE}/upload-portfolio`, {
    method: "POST",
    headers: tok ? { Authorization: `Bearer ${tok}` } : {},
    body: fd,
  });
  if (!res.ok) throw new Error("Upload failed");
  return res.json();
};
