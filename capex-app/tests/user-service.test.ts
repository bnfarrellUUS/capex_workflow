import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";
import { hashPassword, verifyPassword } from "@/lib/auth-service";
import { changePassword } from "@/lib/user-service";
import { createUser, updateUser, adminResetPassword } from "@/lib/user-service";

describe("changePassword", () => {
  beforeEach(resetDb);

  async function makeUser() {
    return prisma.user.create({
      data: {
        username: "jdoe",
        email: "jdoe@uniteduptime.com",
        name: "Jane Doe",
        passwordHash: await hashPassword("OldPass1!"),
        roles: '["REQUESTOR"]',
      },
    });
  }

  it("changes the password when current password is correct", async () => {
    const u = await makeUser();
    const result = await changePassword(u.id, "OldPass1!", "NewPass1!");
    expect(result.ok).toBe(true);
    const updated = await prisma.user.findUniqueOrThrow({ where: { id: u.id } });
    expect(await verifyPassword("NewPass1!", updated.passwordHash)).toBe(true);
  });

  it("rejects when current password is wrong", async () => {
    const u = await makeUser();
    const result = await changePassword(u.id, "wrong", "NewPass1!");
    expect(result).toEqual({ ok: false, error: "Current password is incorrect." });
  });

  it("rejects passwords shorter than 8 characters", async () => {
    const u = await makeUser();
    const result = await changePassword(u.id, "OldPass1!", "short");
    expect(result.ok).toBe(false);
  });
});

describe("admin user management", () => {
  beforeEach(resetDb);

  const input = {
    username: "bsmith",
    email: "bsmith@uniteduptime.com",
    name: "Bob Smith",
    password: "Temp1234!",
    roles: ["REQUESTOR", "APPROVER"] as const,
    divisionId: null,
  };

  it("creates a user with hashed password and roles", async () => {
    const result = await createUser({ ...input, roles: [...input.roles] });
    expect(result.ok).toBe(true);
    const u = await prisma.user.findUniqueOrThrow({ where: { username: "bsmith" } });
    expect(u.roles).toBe('["REQUESTOR","APPROVER"]');
    expect(await verifyPassword("Temp1234!", u.passwordHash)).toBe(true);
  });

  it("rejects duplicate username or email", async () => {
    await createUser({ ...input, roles: [...input.roles] });
    const dupUsername = await createUser({ ...input, roles: [...input.roles], email: "x@uniteduptime.com" });
    expect(dupUsername.ok).toBe(false);
    const dupEmail = await createUser({ ...input, roles: [...input.roles], username: "other" });
    expect(dupEmail.ok).toBe(false);
  });

  it("updates roles, division, and active flag", async () => {
    await createUser({ ...input, roles: [...input.roles] });
    const u = await prisma.user.findUniqueOrThrow({ where: { username: "bsmith" } });
    const division = await prisma.division.create({ data: { number: "200", name: "Dallas" } });
    const result = await updateUser(u.id, {
      name: "Robert Smith",
      email: u.email,
      roles: ["FINANCE"],
      divisionId: division.id,
      active: false,
    });
    expect(result.ok).toBe(true);
    const updated = await prisma.user.findUniqueOrThrow({ where: { id: u.id } });
    expect(updated.name).toBe("Robert Smith");
    expect(updated.roles).toBe('["FINANCE"]');
    expect(updated.divisionId).toBe(division.id);
    expect(updated.active).toBe(false);
  });

  it("admin reset password works and clears lockout", async () => {
    await createUser({ ...input, roles: [...input.roles] });
    const u = await prisma.user.findUniqueOrThrow({ where: { username: "bsmith" } });
    await prisma.user.update({
      where: { id: u.id },
      data: { failedLogins: 5, lockedUntil: new Date(Date.now() + 60_000) },
    });
    const result = await adminResetPassword(u.id, "NewTemp1!");
    expect(result.ok).toBe(true);
    const updated = await prisma.user.findUniqueOrThrow({ where: { id: u.id } });
    expect(await verifyPassword("NewTemp1!", updated.passwordHash)).toBe(true);
    expect(updated.failedLogins).toBe(0);
    expect(updated.lockedUntil).toBeNull();
  });
});
