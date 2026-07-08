import { prisma } from "@/lib/prisma";
import { parseRoles } from "@/lib/roles";
import type { ServiceResult } from "@/lib/user-service";

export async function createDivision(input: {
  number: string;
  name: string;
}): Promise<ServiceResult> {
  const clash = await prisma.division.findUnique({ where: { number: input.number } });
  if (clash) return { ok: false, error: "Division number already exists." };
  await prisma.division.create({ data: { number: input.number, name: input.name } });
  return { ok: true };
}

export async function updateDivision(
  id: string,
  input: { name: string; l1ApproverId: string | null; active: boolean }
): Promise<ServiceResult> {
  if (input.l1ApproverId) {
    const approver = await prisma.user.findUnique({ where: { id: input.l1ApproverId } });
    if (!approver || !approver.active) return { ok: false, error: "Approver not found or inactive." };
    if (!parseRoles(approver.roles).includes("APPROVER")) {
      return { ok: false, error: "Selected user does not have the APPROVER role." };
    }
  }
  await prisma.division.update({
    where: { id },
    data: { name: input.name, l1ApproverId: input.l1ApproverId, active: input.active },
  });
  return { ok: true };
}
