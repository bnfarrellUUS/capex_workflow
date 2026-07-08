import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const prisma = new PrismaClient();

async function main() {
  const passwordHash = await bcrypt.hash("ChangeMe123!", 10);

  const admin = await prisma.user.upsert({
    where: { username: "admin" },
    update: {},
    create: {
      username: "admin",
      email: "capex-admin@uniteduptime.com",
      name: "System Administrator",
      passwordHash,
      roles: '["ADMIN","REQUESTOR"]',
    },
  });

  await prisma.division.upsert({
    where: { number: "100" },
    update: {},
    create: { number: "100", name: "Humble/Houston" },
  });

  for (const t of [
    { level: 1, maxAmount: "10000" },
    { level: 2, maxAmount: "50000" },
    { level: 3, maxAmount: null },
  ]) {
    await prisma.approvalThreshold.upsert({
      where: { level: t.level },
      update: {},
      create: { level: t.level, maxAmount: t.maxAmount },
    });
  }

  await prisma.counter.upsert({
    where: { name: "capexNumber" },
    update: {},
    create: { name: "capexNumber", value: 0 },
  });

  console.log(`Seeded. Admin login: admin / ChangeMe123! (${admin.email})`);
}

main().finally(() => prisma.$disconnect());
