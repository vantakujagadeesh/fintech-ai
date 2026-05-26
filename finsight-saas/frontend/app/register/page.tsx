"use client";

import { useState } from "react";
import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setLoading(true);

    const result = await signIn("credentials", {
      email,
      password,
      action: "register",
      fullName,
      redirect: false,
    });

    setLoading(false);

    if (result?.error) {
      setError(result.error.includes("already") ? "Email already registered. Please sign in." : result.error);
    } else {
      router.push("/dashboard");
    }
  };

  const handleGoogle = () => {
    signIn("google", { callbackUrl: "/dashboard" });
  };

  const inputStyle = {
    width: "100%",
    background: "#1e1e35",
    border: "1px solid rgba(255,255,255,0.15)",
    borderRadius: "12px",
    padding: "12px 16px",
    color: "#f1f5f9",
    fontSize: "0.875rem",
    outline: "none",
    boxSizing: "border-box" as const,
    transition: "border-color 0.2s",
  };

  const labelStyle = {
    display: "block",
    color: "#94a3b8",
    fontSize: "0.875rem",
    marginBottom: "6px",
    fontWeight: 500,
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0a0a12", display: "flex", alignItems: "center", justifyContent: "center", padding: "1rem" }}>
      {/* Gradient blobs */}
      <div style={{ position: "fixed", inset: 0, pointerEvents: "none", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: "5%", right: "15%", width: "450px", height: "450px", background: "radial-gradient(circle, rgba(139,92,246,0.2) 0%, transparent 70%)", borderRadius: "50%" }} />
        <div style={{ position: "absolute", bottom: "5%", left: "10%", width: "350px", height: "350px", background: "radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%)", borderRadius: "50%" }} />
      </div>

      <div style={{ position: "relative", zIndex: 10, width: "100%", maxWidth: "420px" }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "2rem" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: "12px", marginBottom: "0.75rem" }}>
            <div style={{ width: "44px", height: "44px", borderRadius: "12px", background: "linear-gradient(135deg, #6366f1, #3b82f6)", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 0 24px rgba(99,102,241,0.4)" }}>
              <span style={{ color: "white", fontWeight: 900, fontSize: "1.25rem" }}>F</span>
            </div>
            <span style={{ color: "white", fontWeight: 900, fontSize: "1.5rem", letterSpacing: "-0.02em" }}>FinSight AI</span>
          </div>
          <p style={{ color: "#94a3b8", fontSize: "0.875rem" }}>Start free — 5 analyses per day</p>
        </div>

        {/* Card */}
        <div style={{ borderRadius: "20px", border: "1px solid rgba(255,255,255,0.1)", background: "rgba(15,15,30,0.95)", backdropFilter: "blur(20px)", padding: "2rem", boxShadow: "0 25px 50px rgba(0,0,0,0.5)" }}>
          <h1 style={{ color: "white", fontWeight: 800, fontSize: "1.25rem", margin: "0 0 1.5rem 0" }}>Create your account</h1>

          {error && (
            <div style={{ marginBottom: "1rem", padding: "12px 16px", borderRadius: "10px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#f87171", fontSize: "0.875rem" }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <div>
              <label style={labelStyle}>Full Name</label>
              <input
                id="full-name"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Alex Johnson"
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "rgba(99,102,241,0.6)")}
                onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.15)")}
              />
            </div>

            <div>
              <label style={labelStyle}>Email <span style={{ color: "#ef4444" }}>*</span></label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="alex@company.com"
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "rgba(99,102,241,0.6)")}
                onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.15)")}
              />
            </div>

            <div>
              <label style={labelStyle}>Password <span style={{ color: "#ef4444" }}>*</span></label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min 6 characters"
                style={inputStyle}
                onFocus={(e) => (e.target.style.borderColor = "rgba(99,102,241,0.6)")}
                onBlur={(e) => (e.target.style.borderColor = "rgba(255,255,255,0.15)")}
              />
              {password.length > 0 && password.length < 6 && (
                <p style={{ color: "#f87171", fontSize: "0.75rem", marginTop: "4px" }}>At least 6 characters</p>
              )}
            </div>

            <button
              id="register-submit"
              type="submit"
              disabled={loading}
              style={{
                width: "100%",
                padding: "13px",
                borderRadius: "12px",
                border: "none",
                background: loading ? "rgba(99,102,241,0.5)" : "linear-gradient(135deg, #6366f1, #3b82f6)",
                color: "white",
                fontWeight: 700,
                fontSize: "0.9rem",
                cursor: loading ? "not-allowed" : "pointer",
                boxShadow: "0 4px 20px rgba(99,102,241,0.3)",
                transition: "all 0.2s",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                marginTop: "0.5rem",
              }}
            >
              {loading ? (
                <>
                  <span style={{ width: "16px", height: "16px", border: "2px solid rgba(255,255,255,0.3)", borderTopColor: "white", borderRadius: "50%", display: "inline-block", animation: "spin 0.8s linear infinite" }} />
                  Creating account...
                </>
              ) : "Create account"}
            </button>
          </form>

          {/* Divider */}
          <div style={{ position: "relative", margin: "1.25rem 0", textAlign: "center" }}>
            <div style={{ position: "absolute", top: "50%", left: 0, right: 0, height: "1px", background: "rgba(255,255,255,0.08)" }} />
            <span style={{ position: "relative", background: "transparent", padding: "0 12px", color: "#64748b", fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.1em" }}>or</span>
          </div>

          <button
            id="google-register"
            onClick={handleGoogle}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "10px",
              padding: "12px",
              borderRadius: "12px",
              border: "1px solid rgba(255,255,255,0.12)",
              background: "rgba(255,255,255,0.04)",
              color: "#e2e8f0",
              fontWeight: 500,
              fontSize: "0.875rem",
              cursor: "pointer",
              transition: "background 0.2s",
            }}
            onMouseOver={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.08)")}
            onMouseOut={(e) => ((e.currentTarget as HTMLButtonElement).style.background = "rgba(255,255,255,0.04)")}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Continue with Google
          </button>

          <p style={{ marginTop: "1.5rem", textAlign: "center", fontSize: "0.875rem", color: "#64748b" }}>
            Already have an account?{" "}
            <Link href="/login" style={{ color: "#818cf8", fontWeight: 600, textDecoration: "none" }}>
              Sign in
            </Link>
          </p>
        </div>

        {/* Feature pills */}
        <div style={{ display: "flex", justifyContent: "center", gap: "10px", marginTop: "1.5rem", flexWrap: "wrap" }}>
          {["Free tier", "No credit card", "GPT-4o powered"].map((f) => (
            <span key={f} style={{ fontSize: "0.75rem", color: "#64748b", padding: "4px 12px", borderRadius: "999px", border: "1px solid rgba(255,255,255,0.08)", background: "rgba(255,255,255,0.03)" }}>
              ✓ {f}
            </span>
          ))}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
        input::placeholder { color: #475569 !important; }
        input:-webkit-autofill {
          -webkit-box-shadow: 0 0 0 30px #1e1e35 inset !important;
          -webkit-text-fill-color: #f1f5f9 !important;
        }
      `}</style>
    </div>
  );
}
