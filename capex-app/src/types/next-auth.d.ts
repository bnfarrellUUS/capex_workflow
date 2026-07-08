import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface User {
    roles: string[];
    divisionId: string | null;
  }
  interface Session {
    user: {
      id: string;
      roles: string[];
      divisionId: string | null;
    } & DefaultSession["user"];
  }
}
