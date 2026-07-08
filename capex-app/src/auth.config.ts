import type { NextAuthConfig } from "next-auth";

export const authConfig = {
  pages: { signIn: "/login" },
  session: { strategy: "jwt" },
  providers: [], // credentials provider added in auth.ts (needs Prisma, not edge-safe)
  callbacks: {
    authorized({ auth }) {
      return !!auth?.user; // middleware: signed-in users only
    },
    jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.roles = user.roles;
        token.divisionId = user.divisionId;
      }
      return token;
    },
    session({ session, token }) {
      session.user.id = token.id as string;
      session.user.roles = token.roles as string[];
      session.user.divisionId = token.divisionId as string | null;
      return session;
    },
  },
} satisfies NextAuthConfig;
