"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ReportCard } from "@/components/ReportCard";
import { UsageBar } from "@/components/UsageBar";
import {
  submitAnalysis, getJobStatus, getUsage, uploadPortfolio,
  getReports, createCheckoutSession,
  type ReportData, type UsageResponse, type JobStatusResponse,
  type ReportSummary, type PaginatedReports,
} from "@/lib/api";

type Tab = "analyze" | "reports" | "settings";

const AGENT_STEPS = [
  { id: "rag",       icon: "🔍", name: "RAG Retrieval",    desc: "Fetching market data"    },
  { id: "risk",      icon: "⚠️", name: "Risk Analyst",     desc: "Scoring risk factors"    },
  { id: "sentiment", icon: "📊", name: "Sentiment Agent",  desc: "Analyzing market mood"   },
  { id: "forecast",  icon: "🔮", name: "Forecast Agent",   desc: "Predicting outcomes"     },
  { id: "report",    icon: "📋", name: "Report Generator", desc: "Compiling final report"  },
];

const PLANS = [
  {
    id: "free", name: "Free", price: "₹0", period: "forever",
    limit: "5 analyses/day", model: "GPT-4o-mini", color: "#94a3b8",
    features: ["5 queries per day", "Risk + Sentiment analysis", "Basic report"],
  },
  {
    id: "starter", name: "Starter", price: "₹499", period: "/month",
    limit: "50 analyses/day", model: "GPT-4o-mini", color: "#6366f1", popular: true,
    features: ["50 queries per day", "Full report + RAG", "Portfolio PDF upload", "Priority queue"],
  },
  {
    id: "pro", name: "Pro", price: "₹1,999", period: "/month",
    limit: "Unlimited", model: "LLaMA-3 8B", color: "#f59e0b",
    features: ["Unlimited queries", "LLaMA-3 forecast agent", "SEC EDGAR integration", "Priority support"],
  },
];

export default function DashboardPage() {
  const { user, loading: authLoading, logout } = useAuth();
  const router = useRouter();

  const [activeTab,      setActiveTab]      = useState<Tab>("analyze");
  const [company,        setCompany]        = useState("");
  const [query,          setQuery]          = useState("");
  const [jobId,          setJobId]          = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<string>("");
  const [currentReport,  setCurrentReport]  = useState<ReportData | null>(null);
  const [loading,        setLoading]        = useState(false);
  const [usage,          setUsage]          = useState<UsageResponse | null>(null);
  const [uploadFile,     setUploadFile]     = useState<File | null>(null);
  const [uploadStatus,   setUploadStatus]   = useState("");
  const [error,          setError]          = useState("");
  const [activeStep,     setActiveStep]     = useState(-1);
  const [backendOnline,  setBackendOnline]  = useState<boolean | null>(null);

  // Guard: redirect if not logged in
  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  // Backend health check
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/health`,
          { signal: AbortSignal.timeout(2000) }
        );
        setBackendOnline(res.ok);
      } catch { setBackendOnline(false); }
    };
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  // Load usage when user is ready
  useEffect(() => {
    if (user) getUsage().then(setUsage).catch(() => {});
  }, [user]);

  // Poll job status + animate pipeline
  useEffect(() => {
    if (!jobId || !loading) return;
    let stepIdx = 0;
    const stepTimer = setInterval(() => {
      if (stepIdx < AGENT_STEPS.length) setActiveStep(stepIdx++);
    }, 3500);

    const pollTimer = setInterval(async () => {
      try {
        const s: JobStatusResponse = await getJobStatus(jobId);
        setAnalysisStatus(s.status);
        if (s.status === "complete" && s.report) {
          clearInterval(stepTimer); clearInterval(pollTimer);
          setActiveStep(AGENT_STEPS.length);
          setTimeout(() => {
            setCurrentReport(s.report); setLoading(false); setActiveStep(-1);
            getUsage().then(setUsage).catch(() => {});
          }, 600);
        } else if (s.status === "failed") {
          clearInterval(stepTimer); clearInterval(pollTimer);
          setError(s.error ?? "Analysis failed");
          setLoading(false); setActiveStep(-1);
        }
      } catch { /* keep polling */ }
    }, 2000);

    return () => { clearInterval(stepTimer); clearInterval(pollTimer); };
  }, [jobId, loading]);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company.trim() || !query.trim()) return;
    setError(""); setCurrentReport(null); setLoading(true);
    setActiveStep(0); setAnalysisStatus("queued");
    try {
      const r = await submitAnalysis({ company: company.trim(), query: query.trim(), ingest_news: true });
      setJobId(r.job_id);
    } catch (err) {
      setActiveStep(-1); setLoading(false);
      if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
        setError("❌ Cannot reach backend.\nRun: cd finsight-saas && python3 -m uvicorn backend.dev_server:app --port 8000 --reload");
      } else {
        setError(err instanceof Error ? err.message : "Analysis failed");
      }
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploadStatus("Uploading…");
    try {
      const r = await uploadPortfolio(uploadFile);
      setUploadStatus(`✓ Uploaded ${r.chunks} chunks`);
      setUploadFile(null);
    } catch (err) {
      setUploadStatus(`✗ ${err instanceof Error ? err.message : "Upload failed"}`);
    }
  };

  const handleUpgrade = async (planId: string) => {
    if (planId === "free") return;
    try {
      const r = await createCheckoutSession(
        planId as "starter" | "pro",
        `${window.location.origin}/dashboard?success=1`,
        `${window.location.origin}/dashboard`
      );
      window.location.href = r.checkout_url;
    } catch (err) { alert(err instanceof Error ? err.message : "Checkout failed"); }
  };

  if (authLoading || !user) {
    return (
      <div className="min-h-screen bg-[#080810] flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#080810] text-white">
      {/* BG glows */}
      <div className="fixed inset-0 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-blue-600/10 rounded-full blur-3xl" />
      </div>

      {/* Navbar */}
      <nav className="relative z-10 border-b border-white/8 bg-black/20 backdrop-blur-xl sticky top-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-blue-600 flex items-center justify-center">
                <span className="text-white font-black text-sm">F</span>
              </div>
              <span className="font-black text-lg">FinSight AI</span>
            </div>

            <div className="flex items-center gap-1 bg-white/5 rounded-xl p-1">
              {(["analyze", "reports", "settings"] as Tab[]).map(tab => (
                <button key={tab} id={`tab-${tab}`} onClick={() => setActiveTab(tab)}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium capitalize transition-all ${
                    activeTab === tab ? "bg-white/15 text-white" : "text-slate-400 hover:text-white"
                  }`}>{tab}</button>
              ))}
            </div>

            <div className="flex items-center gap-4">
              {usage && (
                <div className="hidden md:block w-48">
                  <UsageBar used={usage.used} limit={usage.limit} plan={usage.plan} />
                </div>
              )}
              <span className="text-sm text-slate-400 hidden sm:block">{user.email}</span>
              <button id="signout-btn" onClick={logout}
                className="text-xs text-slate-500 hover:text-slate-300 transition px-3 py-1.5 rounded-lg hover:bg-white/8">
                Sign out
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

        {/* ── ANALYZE TAB ── */}
        {activeTab === "analyze" && (
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
            {/* Left panel */}
            <div className="lg:col-span-2 space-y-5">
              <div>
                <h1 className="text-2xl font-black">Financial Analysis</h1>
                <p className="text-slate-400 mt-1 text-sm">
                  AI-powered investment intelligence — ask anything about stocks, portfolios, markets
                </p>
              </div>

              {/* Backend status */}
              <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium border ${
                backendOnline === true  ? "border-green-500/30 bg-green-500/10 text-green-400" :
                backendOnline === false ? "border-red-500/30 bg-red-500/10 text-red-400" :
                                         "border-white/10 bg-white/5 text-slate-400"
              }`}>
                <span className={`w-2 h-2 rounded-full ${
                  backendOnline === true ? "bg-green-400 animate-pulse" :
                  backendOnline === false ? "bg-red-400" : "bg-slate-400 animate-pulse"
                }`} />
                {backendOnline === true ? "Backend online" :
                 backendOnline === false ? "Backend offline — start server" : "Checking…"}
              </div>

              <form onSubmit={handleAnalyze} className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-2">Company / Ticker</label>
                  <input id="company-input" type="text" value={company}
                    onChange={e => setCompany(e.target.value)}
                    placeholder="Apple Inc, AAPL, Nifty 50, BTC..."
                    className="w-full bg-white/6 border border-white/12 rounded-xl px-4 py-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition"
                    required />
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-2">Your Financial Question</label>
                  <textarea id="query-input" value={query} onChange={e => setQuery(e.target.value)}
                    placeholder="Should I buy Apple stock? What's the risk of holding AAPL long-term? Compare AAPL vs MSFT..."
                    rows={4} required
                    className="w-full bg-white/6 border border-white/12 rounded-xl px-4 py-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/40 transition resize-none" />
                </div>

                {/* Example queries */}
                <div className="flex flex-wrap gap-2">
                  {[
                    "Should I buy AAPL now?",
                    "Risk analysis for Tesla",
                    "Best EV stocks 2025",
                  ].map(q => (
                    <button key={q} type="button"
                      onClick={() => { setQuery(q); if (!company) setCompany(q.includes("Tesla") ? "TSLA" : q.includes("EV") ? "EV Sector" : "AAPL"); }}
                      className="text-xs px-3 py-1.5 rounded-full border border-violet-500/30 text-violet-400 hover:bg-violet-500/10 transition">
                      {q}
                    </button>
                  ))}
                </div>

                {error && (
                  <div className="p-3 rounded-xl bg-red-950/60 border border-red-500/30 text-red-400 text-sm space-y-1">
                    {error.split("\n").map((line, i) =>
                      i === 0
                        ? <p key={i} className="font-medium">{line}</p>
                        : <code key={i} className="block text-[11px] font-mono bg-red-900/30 px-2 py-1 rounded text-red-300">{line}</code>
                    )}
                  </div>
                )}

                <button id="analyze-btn" type="submit" disabled={loading}
                  className="w-full py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-500 hover:to-blue-500 text-white shadow-lg shadow-violet-500/25 disabled:opacity-50 transition-all flex items-center justify-center gap-2">
                  {loading ? (
                    <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>{analysisStatus === "running" ? "Analyzing…" : "Queuing…"}</span></>
                  ) : <><span>⚡</span><span>Analyze Now</span></>}
                </button>
              </form>

              {/* Portfolio upload */}
              <div className="rounded-xl border border-white/10 bg-white/4 p-4 space-y-3">
                <p className="text-sm font-semibold text-slate-300">📎 Upload Portfolio PDF</p>
                <input id="pdf-upload" type="file" accept=".pdf"
                  onChange={e => setUploadFile(e.target.files?.[0] ?? null)}
                  className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-violet-600/20 file:text-violet-300 file:text-xs cursor-pointer" />
                {uploadFile && (
                  <button id="upload-btn" onClick={handleUpload}
                    className="w-full py-2 rounded-lg text-xs font-medium bg-violet-600/20 text-violet-300 hover:bg-violet-600/30 transition border border-violet-500/30">
                    Upload {uploadFile.name}
                  </button>
                )}
                {uploadStatus && <p className="text-xs text-slate-400">{uploadStatus}</p>}
              </div>

              {/* Agent pipeline steps */}
              <div className="rounded-xl border border-white/8 bg-white/3 p-4">
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Agent Pipeline</p>
                <div className="space-y-1.5">
                  {AGENT_STEPS.map((step, i) => (
                    <div key={step.id} className={`flex items-center gap-2.5 text-xs rounded-lg px-2 py-1.5 transition-all duration-500 ${
                      activeStep === i ? "bg-violet-500/15 border border-violet-500/30" :
                      activeStep > i  ? "opacity-40" : ""
                    }`}>
                      <span className={activeStep === i ? "animate-bounce" : ""}>{step.icon}</span>
                      <div className="flex-1">
                        <span className={`font-medium ${activeStep === i ? "text-violet-300" : "text-slate-400"}`}>{step.name}</span>
                        {activeStep === i && <span className="block text-violet-400/70 text-[10px]">{step.desc}…</span>}
                      </div>
                      {activeStep > i  && <span className="text-green-400">✓</span>}
                      {activeStep === i && <span className="w-3 h-3 border border-violet-400/50 border-t-violet-400 rounded-full animate-spin" />}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Right panel */}
            <div className="lg:col-span-3">
              {loading && !currentReport && (
                <div className="flex flex-col items-center justify-center h-72 rounded-2xl border border-white/8 bg-white/3">
                  <div className="w-14 h-14 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin mb-4" />
                  <p className="text-slate-400 font-medium">
                    {analysisStatus === "running" ? "Multi-agent analysis in progress…" : "Queuing analysis job…"}
                  </p>
                  <p className="text-slate-600 text-xs mt-1">Typically takes 5–15 seconds</p>
                </div>
              )}

              {currentReport && <ReportCard report={currentReport} />}

              {!loading && !currentReport && (
                <div className="flex flex-col items-center justify-center h-72 rounded-2xl border border-dashed border-white/10 bg-white/2 text-center p-8">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-600/20 to-blue-600/20 flex items-center justify-center text-3xl mb-4">🧠</div>
                  <p className="text-slate-400 font-medium">Ready for financial analysis</p>
                  <p className="text-slate-600 text-sm mt-1">Ask anything — stocks, crypto, portfolios, markets</p>
                  <div className="mt-6 grid grid-cols-2 gap-3 text-left w-full max-w-sm">
                    {[
                      { q: "Should I buy RELIANCE stock?",       c: "RELIANCE" },
                      { q: "Analyse risk of holding Nifty 50",   c: "Nifty 50" },
                      { q: "Is Bitcoin a good investment now?",   c: "BTC"      },
                      { q: "Compare TCS vs Infosys for 2025",    c: "TCS"      },
                    ].map(ex => (
                      <button key={ex.q} onClick={() => { setCompany(ex.c); setQuery(ex.q); }}
                        className="text-left p-3 rounded-xl border border-white/8 bg-white/3 hover:bg-white/6 transition text-xs text-slate-400 hover:text-slate-200">
                        {ex.q}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── REPORTS TAB ── */}
        {activeTab === "reports" && <ReportsTab />}

        {/* ── SETTINGS TAB ── */}
        {activeTab === "settings" && (
          <div>
            <div className="mb-6">
              <h1 className="text-2xl font-black">Settings &amp; Billing</h1>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {PLANS.map(p => (
                <div key={p.id} className={`relative rounded-2xl border p-6 transition-all ${
                  "popular" in p && p.popular
                    ? "border-violet-500/50 bg-violet-600/8 shadow-xl shadow-violet-500/10"
                    : "border-white/10 bg-white/4"
                }`}>
                  {"popular" in p && p.popular && (
                    <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                      <span className="px-3 py-1 rounded-full text-xs font-bold bg-gradient-to-r from-violet-600 to-blue-600 text-white">Most Popular</span>
                    </div>
                  )}
                  <div className="mb-5">
                    <h3 className="text-lg font-bold">{p.name}</h3>
                    <div className="flex items-baseline gap-1 mt-2">
                      <span className="text-3xl font-black" style={{ color: p.color }}>{p.price}</span>
                      <span className="text-slate-400 text-sm">{p.period}</span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">{p.limit} • {p.model}</p>
                  </div>
                  <ul className="space-y-2 mb-6">
                    {p.features.map(f => (
                      <li key={f} className="flex items-center gap-2 text-sm text-slate-300">
                        <span style={{ color: p.color }}>✓</span>{f}
                      </li>
                    ))}
                  </ul>
                  <button id={`plan-${p.id}`} onClick={() => handleUpgrade(p.id)}
                    disabled={user.plan === p.id}
                    className="w-full py-3 rounded-xl font-semibold text-sm transition-all disabled:opacity-50"
                    style={user.plan !== p.id && p.id !== "free"
                      ? { background: `linear-gradient(135deg, ${p.color}cc, ${p.color})`, color: "white" }
                      : { background: "rgba(255,255,255,0.08)", color: "#94a3b8" }}>
                    {user.plan === p.id ? "Current Plan" : p.id === "free" ? "Downgrade" : `Upgrade to ${p.name}`}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

/* ── Reports Sub-component ── */
function ReportsTab() {
  const [reports,    setReports]    = useState<ReportSummary[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [page,       setPage]       = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  useEffect(() => {
    setLoading(true);
    getReports(page)
      .then((d: PaginatedReports) => { setReports(d.items); setTotalPages(d.total_pages); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) return (
    <div className="flex items-center justify-center py-16">
      <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
    </div>
  );

  if (reports.length === 0) return (
    <div className="text-center py-16 text-slate-500">
      <p className="text-4xl mb-3">📭</p><p>No analyses yet. Run your first analysis!</p>
    </div>
  );

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-black">Report History</h1>
        <p className="text-slate-400 mt-1 text-sm">All your past financial analyses</p>
      </div>
      <div className="overflow-hidden rounded-2xl border border-white/10">
        <table className="w-full">
          <thead>
            <tr className="border-b border-white/8 bg-white/4">
              {["Company", "Question", "Risk", "Sentiment", "Forecast", "Date"].map(h => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {reports.map(r => (
              <tr key={r.id} className="hover:bg-white/3 transition-colors">
                <td className="px-4 py-4 font-medium">{r.company}</td>
                <td className="px-4 py-4 text-slate-400 text-sm max-w-xs truncate">{r.user_query}</td>
                <td className="px-4 py-4">
                  {r.risk_score != null
                    ? <span className={`text-xs font-bold px-2 py-1 rounded-full ${
                        r.risk_score > 0.7 ? "text-red-400 bg-red-400/10" :
                        r.risk_score > 0.4 ? "text-yellow-400 bg-yellow-400/10" :
                                             "text-green-400 bg-green-400/10"
                      }`}>{Math.round(r.risk_score * 100)}</span>
                    : "—"}
                </td>
                <td className="px-4 py-4">
                  <span className={`text-xs font-semibold capitalize px-2 py-1 rounded-full ${
                    r.sentiment === "bullish" ? "text-green-400 bg-green-400/10" :
                    r.sentiment === "bearish" ? "text-red-400 bg-red-400/10" :
                                               "text-slate-400 bg-slate-400/10"
                  }`}>{r.sentiment ?? "—"}</span>
                </td>
                <td className="px-4 py-4">
                  {r.forecast
                    ? <span className={`text-xs font-bold uppercase px-2 py-1 rounded-full border ${
                        r.forecast === "buy"  ? "text-green-400 bg-green-400/10 border-green-400/30" :
                        r.forecast === "sell" ? "text-red-400 bg-red-400/10 border-red-400/30" :
                                               "text-yellow-400 bg-yellow-400/10 border-yellow-400/30"
                      }`}>{r.forecast}</span>
                    : "—"}
                </td>
                <td className="px-4 py-4 text-slate-500 text-xs">{new Date(r.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 p-4 border-t border-white/8">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white disabled:opacity-40">← Prev</button>
            <span className="text-sm text-slate-400">{page} / {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="px-3 py-1.5 rounded-lg text-sm text-slate-400 hover:text-white disabled:opacity-40">Next →</button>
          </div>
        )}
      </div>
    </div>
  );
}
