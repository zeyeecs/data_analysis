import { existsSync } from "node:fs";
import { join } from "node:path";

import { config } from "dotenv";

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

const webDir = process.cwd();
const localEnv = join(webDir, ".env.local");
const repoDatabaseEnv = join(webDir, "..", "database.env");
if (existsSync(repoDatabaseEnv)) config({ path: repoDatabaseEnv, override: true });
if (existsSync(localEnv)) config({ path: localEnv, override: true });
if (process.env.DATABASE_URL) {
  process.env.DATABASE_URL = normalizeDatabaseUrl(process.env.DATABASE_URL);
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  // recharts → d3-scale 会 import d3-time-format；Next 需显式参与解析/转译
  transpilePackages: ["recharts", "d3-scale", "d3-time", "d3-time-format"],
  webpack: (config) => {
    config.resolve.alias = {
      ...config.resolve.alias,
      "d3-time-format": join(webDir, "node_modules/d3-time-format/src/index.js"),
      "d3-time": join(webDir, "node_modules/d3-time/src/index.js"),
    };
    return config;
  },
  redirects: async () => [
    { source: "/", destination: "/overview", permanent: false },
  ],
};

export default nextConfig;
