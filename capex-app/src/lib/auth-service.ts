import bcrypt from "bcryptjs";
import type { User } from "@prisma/client";
import { prisma } from "@/lib/prisma";

const MAX_FAILURES = 5;
const LOCKOUT_MINUTES = 15;

export async function hashPassword(plain: string): Promise<string> {
  return bcrypt.hash(plain, 10);
}

export async function verifyPassword(plain: string, hash: string): Promise<boolean> {
  return bcrypt.compare(plain, hash);
}

/**
 * Validates credentials. Returns the user on success, null on any failure
 * (unknown user, inactive, locked, or bad password). Applies lockout:
 * 5 consecutive failures locks the account for 15 minutes.
 */
export async function authenticate(username: string, password: string): Promise<User | null> {
  const user = await prisma.user.findUnique({ where: { username } });
  if (!user || !user.active) return null;
  if (user.lockedUntil && user.lockedUntil > new Date()) return null;

  const ok = await verifyPassword(password, user.passwordHash);
  if (!ok) {
    const failures = user.failedLogins + 1;
    await prisma.user.update({
      where: { id: user.id },
      data: {
        failedLogins: failures,
        lockedUntil:
          failures >= MAX_FAILURES
            ? new Date(Date.now() + LOCKOUT_MINUTES * 60_000)
            : null,
      },
    });
    return null;
  }

  if (user.failedLogins > 0 || user.lockedUntil) {
    await prisma.user.update({
      where: { id: user.id },
      data: { failedLogins: 0, lockedUntil: null },
    });
  }
  return user;
}
