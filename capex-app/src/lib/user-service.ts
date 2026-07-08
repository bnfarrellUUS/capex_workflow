import { prisma } from "@/lib/prisma";
import { hashPassword, verifyPassword } from "@/lib/auth-service";
import { serializeRoles, type Role } from "@/lib/roles";

export type ServiceResult = { ok: true } | { ok: false; error: string };

export async function changePassword(
  userId: string,
  current: string,
  next: string
): Promise<ServiceResult> {
  if (next.length < 8) {
    return { ok: false, error: "New password must be at least 8 characters." };
  }
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) return { ok: false, error: "User not found." };
  if (!(await verifyPassword(current, user.passwordHash))) {
    return { ok: false, error: "Current password is incorrect." };
  }
  await prisma.user.update({
    where: { id: userId },
    data: { passwordHash: await hashPassword(next) },
  });
  return { ok: true };
}

export async function createUser(input: {
  username: string;
  email: string;
  name: string;
  password: string;
  roles: Role[];
  divisionId: string | null;
}): Promise<ServiceResult> {
  if (input.password.length < 8) {
    return { ok: false, error: "Password must be at least 8 characters." };
  }
  const clash = await prisma.user.findFirst({
    where: { OR: [{ username: input.username }, { email: input.email }] },
  });
  if (clash) return { ok: false, error: "Username or email already exists." };
  await prisma.user.create({
    data: {
      username: input.username,
      email: input.email,
      name: input.name,
      passwordHash: await hashPassword(input.password),
      roles: serializeRoles(input.roles),
      divisionId: input.divisionId,
    },
  });
  return { ok: true };
}

export async function updateUser(
  id: string,
  input: { name: string; email: string; roles: Role[]; divisionId: string | null; active: boolean }
): Promise<ServiceResult> {
  const clash = await prisma.user.findFirst({
    where: { email: input.email, NOT: { id } },
  });
  if (clash) return { ok: false, error: "Email already in use." };
  await prisma.user.update({
    where: { id },
    data: {
      name: input.name,
      email: input.email,
      roles: serializeRoles(input.roles),
      divisionId: input.divisionId,
      active: input.active,
    },
  });
  return { ok: true };
}

export async function adminResetPassword(id: string, newPassword: string): Promise<ServiceResult> {
  if (newPassword.length < 8) {
    return { ok: false, error: "Password must be at least 8 characters." };
  }
  await prisma.user.update({
    where: { id },
    data: {
      passwordHash: await hashPassword(newPassword),
      failedLogins: 0,
      lockedUntil: null,
    },
  });
  return { ok: true };
}
