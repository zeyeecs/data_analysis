import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

function normalizeDatabaseUrl(url) {
  let value = url.trim();
  if (
    (value.startsWith("'") && value.endsWith("'")) ||
    (value.startsWith('"') && value.endsWith('"'))
  ) {
    value = value.slice(1, -1);
  }
  const parsed = new URL(value);
  parsed.searchParams.delete("channel_binding");
  if (!parsed.searchParams.has("sslmode")) parsed.searchParams.set("sslmode", "require");
  if (!parsed.searchParams.has("connect_timeout")) parsed.searchParams.set("connect_timeout", "15");
  return parsed.toString();
}

function extractUrl(line) {
  const raw = line.replace(/^DATABASE_URL\s*=\s*/, "").trim();
  return normalizeDatabaseUrl(raw);
}

const webDir = join(import.meta.dirname, "..");
const repoDatabaseEnv = join(webDir, "..", "database.env");
const target = join(webDir, ".env.local");

if (!existsSync(repoDatabaseEnv)) {
  console.error("未找到 ../database.env，请先复制 database.env.example 并填写 DATABASE_URL。");
  process.exit(1);
}

const raw = readFileSync(repoDatabaseEnv, "utf8");
const line = raw
  .split("\n")
  .map((l) => l.trim())
  .find((l) => l.startsWith("DATABASE_URL"));

if (!line) {
  console.error("database.env 中缺少 DATABASE_URL。");
  process.exit(1);
}

const url = extractUrl(line);
writeFileSync(
  target,
  `# 由 npm run env:sync 从仓库根 database.env 生成，勿提交\nDATABASE_URL=${url}\n`,
  "utf8",
);
console.log(`已写入 ${target}`);
