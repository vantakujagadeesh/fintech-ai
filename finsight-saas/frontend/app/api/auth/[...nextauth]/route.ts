import NextAuth, { type AuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";
import CredentialsProvider from "next-auth/providers/credentials";

const authOptions: AuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),

    CredentialsProvider({
      name: "Email",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
        action: { label: "Action", type: "text" },
        fullName: { label: "Full Name", type: "text" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error("Email and password are required");
        }

        // Try FastAPI backend first, fall back to local auth
        const backendUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        let response: Response | null = null;

        try {
          if (credentials.action === "register") {
            response = await fetch(`${backendUrl}/auth/register`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                email: credentials.email,
                password: credentials.password,
                full_name: credentials.fullName,
              }),
              signal: AbortSignal.timeout(3000), // 3s timeout
            });
          } else {
            response = await fetch(`${backendUrl}/auth/token`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                email: credentials.email,
                password: credentials.password,
              }),
              signal: AbortSignal.timeout(3000),
            });
          }
        } catch {
          // Backend unavailable — fall through to local auth
          response = null;
        }

        // If backend responded, use it
        if (response && response.ok) {
          const data = await response.json();
          return {
            id: data.user_id,
            email: data.email,
            name: credentials.fullName ?? data.email,
            accessToken: data.access_token,
            plan: data.plan ?? "free",
          };
        }

        // Backend unavailable or returned error — use local auth fallback
        const localResponse = await fetch(
          new URL("/api/auth/local", process.env.NEXTAUTH_URL ?? "http://localhost:3000"),
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              action: credentials.action ?? "login",
              email: credentials.email,
              password: credentials.password,
              fullName: credentials.fullName,
            }),
          }
        );

        const localData = await localResponse.json();

        if (!localResponse.ok) {
          throw new Error(localData.error ?? "Authentication failed");
        }

        return {
          id: localData.user_id,
          email: localData.email,
          name: credentials.fullName ?? localData.email,
          accessToken: localData.access_token,
          plan: localData.plan ?? "free",
        };
      },
    }),
  ],

  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken = (user as { accessToken?: string }).accessToken;
        token.plan = (user as { plan?: string }).plan ?? "free";
        token.userId = user.id;
      }
      return token;
    },

    async session({ session, token }) {
      (session as typeof session & { accessToken?: string }).accessToken = token.accessToken as string;
      (session as typeof session & { plan?: string }).plan = (token.plan as string) ?? "free";
      (session as typeof session & { userId?: string }).userId = token.userId as string;
      return session;
    },
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },

  session: {
    strategy: "jwt",
    maxAge: 60 * 60 * 24 * 7,
  },

  secret: process.env.NEXTAUTH_SECRET ?? "finsight-fallback-secret",
};

const handler = NextAuth(authOptions);
export { handler as GET, handler as POST };
