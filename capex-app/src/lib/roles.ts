export const ROLES = ["REQUESTOR", "APPROVER", "FINANCE", "ADMIN"] as const;
export type Role = (typeof ROLES)[number];

export function parseRoles(json: string): Role[] {
  const parsed: unknown = JSON.parse(json);
  if (!Array.isArray(parsed)) throw new Error("roles must be a JSON array");
  for (const r of parsed) {
    if (!ROLES.includes(r as Role)) throw new Error(`Unknown role: ${String(r)}`);
  }
  return parsed as Role[];
}

export function serializeRoles(roles: Role[]): string {
  return JSON.stringify(roles);
}
