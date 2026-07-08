import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { authConfig } from "@/auth.config";
import { authenticate } from "@/lib/auth-service";
import { parseRoles } from "@/lib/roles";

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  providers: [
    Credentials({
      credentials: { username: {}, password: {} },
      async authorize(credentials) {
        const user = await authenticate(
          String(credentials?.username ?? ""),
          String(credentials?.password ?? "")
        );
        if (!user) return null;
        return {
          id: user.id,
          name: user.name,
          email: user.email,
          roles: parseRoles(user.roles),
          divisionId: user.divisionId,
        };
      },
    }),
  ],
});
