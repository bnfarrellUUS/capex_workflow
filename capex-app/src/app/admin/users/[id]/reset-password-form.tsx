"use client";

import { useActionState } from "react";
import { resetPasswordAction } from "../actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ResetPasswordForm({ userId }: { userId: string }) {
  const [message, formAction, pending] = useActionState(resetPasswordAction, undefined);
  return (
    <Card className="max-w-lg">
      <CardHeader><CardTitle>Reset Password</CardTitle></CardHeader>
      <CardContent>
        <form action={formAction} className="space-y-4">
          <input type="hidden" name="id" value={userId} />
          <div className="space-y-1">
            <Label htmlFor="password">New temporary password (min 8 characters)</Label>
            <Input id="password" name="password" type="text" minLength={8} required />
          </div>
          {message && <p className="text-sm text-muted-foreground">{message}</p>}
          <Button type="submit" variant="outline" disabled={pending}>Reset password</Button>
        </form>
      </CardContent>
    </Card>
  );
}
