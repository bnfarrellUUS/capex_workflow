"use client";

import { useActionState } from "react";
import { ROLES } from "@/lib/roles";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Division = { id: string; number: string; name: string };
type UserData = {
  id: string;
  username: string;
  email: string;
  name: string;
  roles: string[];
  divisionId: string | null;
  active: boolean;
};

export function UserForm({
  action,
  divisions,
  user,
}: {
  action: (prev: string | undefined, formData: FormData) => Promise<string | undefined>;
  divisions: Division[];
  user?: UserData;
}) {
  const [error, formAction, pending] = useActionState(action, undefined);

  return (
    <form action={formAction} className="max-w-lg space-y-4">
      {user && <input type="hidden" name="id" value={user.id} />}
      <div className="space-y-1">
        <Label htmlFor="username">Username</Label>
        <Input id="username" name="username" defaultValue={user?.username} required
          disabled={!!user} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="name">Full name</Label>
        <Input id="name" name="name" defaultValue={user?.name} required />
      </div>
      <div className="space-y-1">
        <Label htmlFor="email">Email</Label>
        <Input id="email" name="email" type="email" defaultValue={user?.email} required />
      </div>
      {!user && (
        <div className="space-y-1">
          <Label htmlFor="password">Temporary password (min 8 characters)</Label>
          <Input id="password" name="password" type="text" minLength={8} required />
        </div>
      )}
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">Roles</legend>
        {ROLES.map((r) => (
          <label key={r} className="flex items-center gap-2 text-sm">
            <input type="checkbox" name={`role_${r}`}
              defaultChecked={user?.roles.includes(r) ?? r === "REQUESTOR"} />
            {r.charAt(0) + r.slice(1).toLowerCase()}
          </label>
        ))}
      </fieldset>
      <div className="space-y-1">
        <Label htmlFor="divisionId">Division</Label>
        <select id="divisionId" name="divisionId" defaultValue={user?.divisionId ?? "none"}
          className="w-full rounded-md border px-3 py-2 text-sm">
          <option value="none">— None —</option>
          {divisions.map((d) => (
            <option key={d.id} value={d.id}>{d.number} — {d.name}</option>
          ))}
        </select>
      </div>
      {user && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="active" defaultChecked={user.active} /> Active
        </label>
      )}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      <Button type="submit" disabled={pending}>{user ? "Save changes" : "Create user"}</Button>
    </form>
  );
}
