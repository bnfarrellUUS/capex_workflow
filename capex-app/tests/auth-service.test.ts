import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";
import { hashPassword, verifyPassword, authenticate } from "@/lib/auth-service";
import { parseRoles, serializeRoles } from "@/lib/roles";

async function makeUser(overrides: Record<string, unknown> = {}) {
  return prisma.user.create({
    data: {
      username: "jdoe",
      email: "jdoe@uniteduptime.com",
      name: "Jane Doe",
      passwordHash: await hashPassword("CorrectHorse1!"),
      roles: '["REQUESTOR"]',
      ...overrides,
    },
  });
}

describe("roles helpers", () => {
  it("round-trips roles", () => {
    expect(parseRoles(serializeRoles(["ADMIN", "APPROVER"]))).toEqual(["ADMIN", "APPROVER"]);
  });
  it("rejects unknown roles", () => {
    expect(() => parseRoles('["SUPERUSER"]')).toThrow();
  });
});

describe("password hashing", () => {
  it("verifies a correct password and rejects a wrong one", async () => {
    const hash = await hashPassword("s3cret!");
    expect(await verifyPassword("s3cret!", hash)).toBe(true);
    expect(await verifyPassword("nope", hash)).toBe(false);
  });
});

describe("authenticate", () => {
  beforeEach(resetDb);

  it("returns the user for valid credentials", async () => {
    await makeUser();
    const user = await authenticate("jdoe", "CorrectHorse1!");
    expect(user?.username).toBe("jdoe");
  });

  it("returns null for a wrong password and increments failedLogins", async () => {
    await makeUser();
    expect(await authenticate("jdoe", "wrong")).toBeNull();
    const u = await prisma.user.findUnique({ where: { username: "jdoe" } });
    expect(u?.failedLogins).toBe(1);
  });

  it("returns null for unknown user and inactive user", async () => {
    expect(await authenticate("ghost", "x")).toBeNull();
    await makeUser({ active: false });
    expect(await authenticate("jdoe", "CorrectHorse1!")).toBeNull();
  });

  it("locks the account after 5 failures", async () => {
    await makeUser();
    for (let i = 0; i < 5; i++) await authenticate("jdoe", "wrong");
    const u = await prisma.user.findUnique({ where: { username: "jdoe" } });
    expect(u?.lockedUntil).not.toBeNull();
    // correct password still rejected while locked
    expect(await authenticate("jdoe", "CorrectHorse1!")).toBeNull();
  });

  it("resets failure count on success", async () => {
    await makeUser();
    await authenticate("jdoe", "wrong");
    await authenticate("jdoe", "CorrectHorse1!");
    const u = await prisma.user.findUnique({ where: { username: "jdoe" } });
    expect(u?.failedLogins).toBe(0);
  });
});
