import type { AuthOptions } from "next-auth";
import CredentialsProvider from "next-auth/providers/credentials";
import { login } from "./api";

export const authOptions: AuthOptions = {
  session: { strategy: "jwt" },
  secret: process.env.NEXTAUTH_SECRET,
  pages: { signIn: "/login" },
  providers: [
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
          return { id: String(user.id), email: user.email, isAdmin: user.is_admin, plan: user.plan };
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user, trigger, session }) {
      if (user) {
        token.userId = (user as { id: string }).id;
        token.isAdmin = (user as { isAdmin?: boolean }).isAdmin ?? false;
        token.plan = (user as { plan?: string }).plan ?? "free";
      }
      // allow the client to refresh the plan after a mock subscribe
      if (trigger === "update" && session?.plan) {
        token.plan = session.plan;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        const u = session.user as { id?: string; isAdmin?: boolean; plan?: string };
        u.id = token.userId as string;
        u.isAdmin = token.isAdmin as boolean;
        u.plan = (token.plan as string) ?? "free";
      }
      return session;
    },
  },
};
