import { describe, it, expect, beforeEach } from "vitest";
import { prisma } from "@/lib/prisma";
import { resetDb } from "./helpers/db";

describe("schema", () => {
  beforeEach(resetDb);

  it("creates and reads a user with a division", async () => {
    const division = await prisma.division.create({
      data: { number: "100", name: "Humble/Houston" },
    });
    const user = await prisma.user.create({
      data: {
        username: "jdoe",
        email: "jdoe@uniteduptime.com",
        name: "Jane Doe",
        passwordHash: "x",
        roles: '["REQUESTOR"]',
        divisionId: division.id,
      },
    });
    const found = await prisma.user.findUnique({
      where: { username: "jdoe" },
      include: { division: true },
    });
    expect(found?.email).toBe("jdoe@uniteduptime.com");
    expect(found?.division?.name).toBe("Humble/Houston");
    expect(found?.id).toBe(user.id);
  });
});
