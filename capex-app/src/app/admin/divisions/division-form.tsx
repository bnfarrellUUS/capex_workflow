"use client";

import { useActionState } from "react";
import { createDivisionAction, updateDivisionAction } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Approver = { id: string; name: string };
type DivisionData = {
  id: string; number: string; name: string;
  l1ApproverId: string | null; active: boolean;
};

export function NewDivisionForm() {
  const [message, formAction, pending] = useActionState(createDivisionAction, undefined);
  return (
    <form action={formAction} className="flex items-end gap-2">
      <div>
        <label className="text-sm font-medium">Number</label>
        <Input name="number" required className="w-28" />
      </div>
      <div className="flex-1">
        <label className="text-sm font-medium">Name</label>
        <Input name="name" required />
      </div>
      <Button type="submit" disabled={pending}>Add</Button>
      {message && <p className="pb-2 text-sm text-muted-foreground">{message}</p>}
    </form>
  );
}

export function EditDivisionRow({ division, approvers }: { division: DivisionData; approvers: Approver[] }) {
  const [message, formAction, pending] = useActionState(updateDivisionAction, undefined);
  return (
    <form action={formAction} className="flex items-center gap-2 border-b p-3 last:border-0">
      <input type="hidden" name="id" value={division.id} />
      <span className="w-20 text-sm font-mono">{division.number}</span>
      <Input name="name" defaultValue={division.name} className="w-56" />
      <select name="l1ApproverId" defaultValue={division.l1ApproverId ?? "none"}
        className="rounded-md border bg-background px-2 py-1.5 text-sm">
        <option value="none">— No L1 approver —</option>
        {approvers.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
      </select>
      <label className="flex items-center gap-1 text-sm">
        <input type="checkbox" name="active" defaultChecked={division.active} /> Active
      </label>
      <Button type="submit" size="sm" variant="outline" disabled={pending}>Save</Button>
      {message && <span className="text-xs text-muted-foreground">{message}</span>}
    </form>
  );
}
