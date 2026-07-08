"use server";

import { revalidatePath } from "next/cache";
import { requireRole } from "@/lib/authz";
import { updateThresholds } from "@/lib/threshold-service";

export async function updateThresholdsAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const l2 = String(formData.get("l2ApproverId") ?? "none");
  const l3 = String(formData.get("l3ApproverId") ?? "none");
  const result = await updateThresholds({
    l1Max: Number(formData.get("l1Max")),
    l2Max: Number(formData.get("l2Max")),
    l2ApproverId: l2 === "none" ? null : l2,
    l3ApproverId: l3 === "none" ? null : l3,
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/thresholds");
  return "Thresholds updated.";
}
