import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
    globalSetup: "./tests/global-setup.ts",
    env: { DATABASE_URL: "file:./test.db" },
    fileParallelism: false, // one shared SQLite test db
  },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
