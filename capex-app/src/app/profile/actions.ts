"use server";

import { requireSession } from "@/lib/authz";
import { changePassword } from "@/lib/user-service";

export async function changePasswordAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string> {
  const session = await requireSession();
  const result = await changePassword(
    session.user.id,
    String(formData.get("current") ?? ""),
    String(formData.get("next") ?? "")
  );
  return result.ok ? "Password changed." : result.error;
}
