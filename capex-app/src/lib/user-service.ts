import { prisma } from "@/lib/prisma";
import { hashPassword, verifyPassword } from "@/lib/auth-service";

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
