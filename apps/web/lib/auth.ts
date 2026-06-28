import type { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import GoogleProvider from "next-auth/providers/google";
import { login, oauthUpsert } from "./api";

const providers: AuthOptions["providers"] = [
  CredentialsProvider({
    name: "Credentials",
    credentials: {
      email: { label: "Email", type: "email" },
      password: { label: "Password", type: "password" },
    },
    async authorize(credentials) {
      if (!credentials?.email || !credentials?.password) return null;
      try {
        const user = await login(credentials.email, credentials.password);
        return {
          id: String(user.id),
          email: user.email,
          isAdmin: user.is_admin,
          plan: user.plan,
          fullName: user.full_name,
        };
      } catch {
        return null;
      }
    },
  }),
];

// Google is a "trusted auth provider" — only enabled when credentials are
// configured (GOOGLE_CLIENT_ID/SECRET), so the app still runs without them.
if (process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET) {
  providers.push(
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    })
  );
}

export const authOptions: AuthOptions = {
  session: { strategy: "jwt" },
  secret: process.env.NEXTAUTH_SECRET,
  pages: { signIn: "/login" },
  providers,
  callbacks: {
    async signIn({ user, account }) {
      // Bridge a trusted-provider sign-in to our backend: Google has already
      // verified the email, so we create/find the matching account there and
      // attach its real id/plan/admin flag onto the NextAuth user object.
      if (account?.provider === "google" && user.email) {
        try {
          const backendUser = await oauthUpsert(user.email, user.name ?? null, "google");
          (user as { id: string }).id = String(backendUser.id);
          (user as { isAdmin?: boolean }).isAdmin = backendUser.is_admin;
          (user as { plan?: string }).plan = backendUser.plan;
          (user as { fullName?: string | null }).fullName = backendUser.full_name;
          return true;
        } catch {
          return false; // backend rejected the bridge (e.g. misconfigured secret)
        }
      }
      return true;
    },
    async jwt({ token, user, trigger, session }) {
      if (user) {
        token.userId = (user as { id: string }).id;
        token.isAdmin = (user as { isAdmin?: boolean }).isAdmin ?? false;
        token.plan = (user as { plan?: string }).plan ?? "free";
        token.fullName = (user as { fullName?: string | null }).fullName ?? null;
      }
      // allow the client to refresh the plan after a mock subscribe
      if (trigger === "update" && session?.plan) {
        token.plan = session.plan;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        const u = session.user as { id?: string; isAdmin?: boolean; plan?: string; fullName?: string | null };
        u.id = token.userId as string;
        u.isAdmin = token.isAdmin as boolean;
        u.plan = (token.plan as string) ?? "free";
        u.fullName = (token.fullName as string | null) ?? null;
      }
      return session;
    },
  },
};
