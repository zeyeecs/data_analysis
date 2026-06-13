import { existsSync } from "node:fs";
import { join } from "node:path";

import { config } from "dotenv";

import { normalizeDatabaseUrl } from "@/lib/database-url";

export function loadDatabaseEnv() {
  const webDir = process.cwd();
  const localEnv = join(webDir, ".env.local");
  const repoDatabaseEnv = join(webDir, "..", "database.env");

  // database.env 覆盖 shell 里可能错误的 DATABASE_URL
  if (existsSync(repoDatabaseEnv)) {
    config({ path: repoDatabaseEnv, override: true });
  }
  if (existsSync(localEnv)) {
    config({ path: localEnv, override: true });
  }

  if (process.env.DATABASE_URL) {
    process.env.DATABASE_URL = normalizeDatabaseUrl(process.env.DATABASE_URL);
  }
}

loadDatabaseEnv();
