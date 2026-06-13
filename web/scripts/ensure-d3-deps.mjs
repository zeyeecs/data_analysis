#!/usr/bin/env node
/**
 * recharts → d3-scale 需要完整的 d3-time-format（含 src/index.js）。
 * 偶发 npm 会留下空目录，导致 Next 编译报 Module not found。
 */
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const required = [
  "d3-time-format/src/index.js",
  "d3-scale/src/index.js",
  "d3-time/src/index.js",
];

const missing = required.filter((rel) => !existsSync(join(webRoot, "node_modules", rel)));

if (missing.length === 0) {
  process.exit(0);
}

console.warn("[ensure-d3-deps] 修复不完整的 d3 依赖:", missing.join(", "));
// 损坏的安装可能只剩 locale.js，需删掉再装完整包
for (const pkg of ["d3-time-format", "d3-time", "d3-scale"]) {
  execSync(`rm -rf node_modules/${pkg}`, { cwd: webRoot, stdio: "inherit" });
}
execSync("npm install d3-time-format@4.1.0 d3-time@3.1.0 d3-scale@4.0.2", {
  cwd: webRoot,
  stdio: "inherit",
});

const stillMissing = required.filter((rel) => !existsSync(join(webRoot, "node_modules", rel)));
if (stillMissing.length > 0) {
  console.error("[ensure-d3-deps] 仍缺失:", stillMissing.join(", "));
  process.exit(1);
}
