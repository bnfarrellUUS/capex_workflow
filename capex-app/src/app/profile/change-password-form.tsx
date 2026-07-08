"use client";

import { useActionState } from "react";
import { changePasswordAction } from "./actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ChangePasswordForm() {
  const [message, formAction, pending] = useActionState(changePasswordAction, undefined);
  return (
    <Card>
      <CardHeader><CardTitle>Change Password</CardTitle></CardHeader>
      <CardContent>
        <form action={formAction} className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="current">Current password</Label>
            <Input id="current" name="current" type="password" required />
          </div>
          <div className="space-y-1">
            <Label htmlFor="next">New password (min 8 characters)</Label>
            <Input id="next" name="next" type="password" minLength={8} required />
          </div>
          {message && <p className="text-sm text-muted-foreground">{message}</p>}
          <Button type="submit" disabled={pending}>Change password</Button>
        </form>
      </CardContent>
    </Card>
  );
}
