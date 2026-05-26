/**
 * Local user store — works without the Python backend.
 * Stores users in memory (persists for dev session).
 * In production, all auth goes through the FastAPI backend.
 */

import { NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { SignJWT } from "jose";

// In-memory user store for development fallback
const users: Map<
  string,
  { id: string; email: string; hashedPassword: string; fullName: string; plan: string }
> = new Map();

const JWT_SECRET = process.env.NEXTAUTH_SECRET ?? "finsight-dev-secret-32chars-minimum";

async function mintToken(userId: string, email: string, plan: string): Promise<string> {
  const secret = new TextEncoder().encode(JWT_SECRET);
  return new SignJWT({ sub: userId, email, plan })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("7d")
    .sign(secret);
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { action, email, password, fullName } = body;

    if (!email || !password) {
      return NextResponse.json({ error: "Email and password are required" }, { status: 400 });
    }

    if (action === "register") {
      if (users.has(email)) {
        return NextResponse.json({ error: "Email already registered" }, { status: 409 });
      }

      const hashedPassword = await bcrypt.hash(password, 10);
      const id = crypto.randomUUID();

      users.set(email, { id, email, hashedPassword, fullName: fullName ?? "", plan: "free" });

      const token = await mintToken(id, email, "free");
      return NextResponse.json({ user_id: id, email, plan: "free", access_token: token });
    }

    if (action === "login" || !action) {
      const user = users.get(email);
      if (!user) {
        return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
      }

      const valid = await bcrypt.compare(password, user.hashedPassword);
      if (!valid) {
        return NextResponse.json({ error: "Invalid email or password" }, { status: 401 });
      }

      const token = await mintToken(user.id, user.email, user.plan);
      return NextResponse.json({
        user_id: user.id,
        email: user.email,
        plan: user.plan,
        access_token: token,
      });
    }

    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  } catch (err) {
    console.error("Local auth error:", err);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
