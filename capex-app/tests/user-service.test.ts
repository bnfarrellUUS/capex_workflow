import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";
import { hashPassword, verifyPassword } from "@/lib/auth-service";
import { changePassword } from "@/lib/user-service";

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
