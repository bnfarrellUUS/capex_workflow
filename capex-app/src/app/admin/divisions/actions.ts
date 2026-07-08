"use server";

import { revalidatePath } from "next/cache";
import { requireRole } from "@/lib/authz";
import { createDivision, updateDivision } from "@/lib/division-service";

export async function createDivisionAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const result = await createDivision({
    number: String(formData.get("number") ?? "").trim(),
    name: String(formData.get("name") ?? "").trim(),
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/divisions");
  return "Division created.";
}

export async function updateDivisionAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const l1 = String(formData.get("l1ApproverId") ?? "none");
  const result = await updateDivision(String(formData.get("id")), {
    name: String(formData.get("name") ?? "").trim(),
    l1ApproverId: l1 === "none" ? null : l1,
    active: formData.get("active") === "on",
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/divisions");
  return "Division updated.";
}
