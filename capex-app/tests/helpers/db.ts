import { prisma } from "@/lib/prisma";

/** Delete all rows in FK-safe order. Call in beforeEach. */
export async function resetDb() {
  await prisma.notificationLog.deleteMany();
  await prisma.approvalAction.deleteMany();
  await prisma.attachment.deleteMany();
  await prisma.equipmentItem.deleteMany();
  await prisma.capexRequest.deleteMany();
  await prisma.approvalThreshold.deleteMany();
  await prisma.user.updateMany({ data: { delegateId: null } });
  await prisma.division.updateMany({ data: { l1ApproverId: null } });
  await prisma.user.deleteMany();
  await prisma.division.deleteMany();
  await prisma.counter.deleteMany();
  await prisma.appSetting.deleteMany();
}
