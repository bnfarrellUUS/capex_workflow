"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { requireRole } from "@/lib/authz";
import { ROLES, type Role } from "@/lib/roles";
import { createUser, updateUser, adminResetPassword } from "@/lib/user-service";

function rolesFromForm(formData: FormData): Role[] {
  return ROLES.filter((r) => formData.get(`role_${r}`) === "on");
}

function divisionFromForm(formData: FormData): string | null {
  const v = String(formData.get("divisionId") ?? "");
  return v === "" || v === "none" ? null : v;
}

export async function createUserAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const result = await createUser({
    username: String(formData.get("username") ?? "").trim(),
    email: String(formData.get("email") ?? "").trim(),
    name: String(formData.get("name") ?? "").trim(),
    password: String(formData.get("password") ?? ""),
    roles: rolesFromForm(formData),
    divisionId: divisionFromForm(formData),
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/users");
  redirect("/admin/users");
}

export async function updateUserAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const result = await updateUser(String(formData.get("id")), {
    name: String(formData.get("name") ?? "").trim(),
    email: String(formData.get("email") ?? "").trim(),
    roles: rolesFromForm(formData),
    divisionId: divisionFromForm(formData),
    active: formData.get("active") === "on",
  });
  if (!result.ok) return result.error;
  revalidatePath("/admin/users");
  redirect("/admin/users");
}

export async function resetPasswordAction(
  _prev: string | undefined,
  formData: FormData
): Promise<string | undefined> {
  await requireRole("ADMIN");
  const result = await adminResetPassword(
    String(formData.get("id")),
    String(formData.get("password") ?? "")
  );
  return result.ok ? "Password reset." : result.error;
}
