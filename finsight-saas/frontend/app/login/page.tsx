"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode]         = useState<"login" | "register">("login");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [name, setName]         = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setLoading(true);
    try {
      if (mode === "register") await register(email, password, name || undefined);
      else                     await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#080810] flex items-center justify-center px-4 relative overflow-hidden">
      {/* Gradient orbs */}
      <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-violet-600/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-blue-600/15 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-indigo-800/8 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md relative">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-blue-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
              <span className="text-white font-black text-lg">F</span>
            </div>
            <span className="text-white font-black text-2xl tracking-tight">FinSight AI</span>
          </div>
          <p className="text-slate-400 text-sm">AI-powered financial analysis platform</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-white/10 bg-white/5 backdrop-blur-xl p-8 shadow-2xl">
          {/* Toggle */}
          <div className="flex bg-white/5 rounded-xl p-1 mb-6">
            {(["login", "register"] as const).map((m) => (
              <button key={m} onClick={() => { setMode(m); setError(""); }}
                className={`flex-1 py-2 rounded-lg text-sm font-medium capitalize transition-all ${
                  mode === m ? "bg-white/15 text-white shadow" : "text-slate-400 hover:text-white"
                }`}>
                {m === "login" ? "Sign In" : "Create Account"}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === "register" && (
              <div>
                <label className="block text-xs text-slate-400 mb-1.5 font-medium">Full Name (optional)</label>
                <input type="text" value={name} onChange={e => setName(e.target.value)}
                  placeholder="Jagadeesh Vantaku"
                  className="w-full bg-white/6 border border-white/12 rounded-xl px-4 py-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/40 transition" />
              </div>
            )}
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">Email</label>
              <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full bg-white/6 border border-white/12 rounded-xl px-4 py-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/40 transition" />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5 font-medium">Password</label>
              <input type="password" required value={password} onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-white/6 border border-white/12 rounded-xl px-4 py-3 text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-violet-500/40 focus:border-violet-500/40 transition" />
            </div>

            {error && (
              <div className="p-3 rounded-xl bg-red-950/60 border border-red-500/30 text-red-400 text-sm">{error}</div>
            )}

            <button type="submit" disabled={loading}
              className="w-full py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-500 hover:to-blue-500 text-white shadow-lg shadow-violet-500/25 disabled:opacity-50 transition-all duration-200 flex items-center justify-center gap-2 mt-2">
              {loading ? (
                <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /><span>Please wait...</span></>
              ) : (
                <span>{mode === "login" ? "Sign In →" : "Create Account →"}</span>
              )}
            </button>
          </form>

          <p className="text-center text-xs text-slate-600 mt-6">
            No credit card required • Free tier available
          </p>
        </div>

        {/* Features hint */}
        <div className="grid grid-cols-3 gap-3 mt-6">
          {[
            { icon: "🔍", label: "Real-time RAG" },
            { icon: "⚡", label: "AI Analysis" },
            { icon: "📊", label: "Risk Scoring" },
          ].map(f => (
            <div key={f.label} className="text-center p-3 rounded-xl border border-white/6 bg-white/3">
              <div className="text-xl mb-1">{f.icon}</div>
              <div className="text-xs text-slate-500">{f.label}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
