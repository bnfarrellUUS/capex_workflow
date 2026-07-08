"use client";

import { useActionState } from "react";
import { updateThresholdsAction } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Approver = { id: string; name: string };
type Thresholds = {
  l1Max: string; l2Max: string;
  l2ApproverId: string | null; l3ApproverId: string | null;
};

export function ThresholdForm({ current, approvers }: { current: Thresholds; approvers: Approver[] }) {
  const [message, formAction, pending] = useActionState(updateThresholdsAction, undefined);

  const approverSelect = (name: string, value: string | null) => (
    <select name={name} defaultValue={value ?? "none"}
      className="w-full rounded-md border bg-background px-3 py-2 text-sm">
      <option value="none">— Not assigned —</option>
      {approvers.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
    </select>
  );

  return (
    <form action={formAction} className="max-w-xl space-y-6">
      <div className="rounded-lg border bg-card p-4">
        <h2 className="mb-2 font-medium">Level 1 — Division Manager</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Approver is set per division (Admin → Divisions). Requests up to this amount
          stop after Level 1 approval.
        </p>
        <Label htmlFor="l1Max">Approves up to ($)</Label>
        <Input id="l1Max" name="l1Max" type="number" min="1" step="0.01"
          defaultValue={current.l1Max} required />
      </div>
      <div className="rounded-lg border bg-card p-4">
        <h2 className="mb-2 font-medium">Level 2 — VP / Director (company-wide)</h2>
        <Label htmlFor="l2Max">Approves up to ($)</Label>
        <Input id="l2Max" name="l2Max" type="number" min="1" step="0.01"
          defaultValue={current.l2Max} required className="mb-3" />
        <Label>Approver</Label>
        {approverSelect("l2ApproverId", current.l2ApproverId)}
      </div>
      <div className="rounded-lg border bg-card p-4">
        <h2 className="mb-2 font-medium">Level 3 — CFO / CEO (company-wide)</h2>
        <p className="mb-3 text-sm text-muted-foreground">No upper limit — required for all requests above the Level 2 limit.</p>
        <Label>Approver</Label>
        {approverSelect("l3ApproverId", current.l3ApproverId)}
      </div>
      {message && <p className="text-sm text-muted-foreground">{message}</p>}
      <Button type="submit" disabled={pending}>Save thresholds</Button>
    </form>
  );
}
