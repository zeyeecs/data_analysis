import { existsSync } from "node:fs";
import { join } from "node:path";

import {
  getRemoteAgentAvailability,
  isRemoteAgentConfigured,
} from "@/lib/ai-tasks/remote-agent";

export function isServerlessDeployment(): boolean {
  return Boolean(process.env.VERCEL);
}

export function getRepoRoot(): string {
  return join(process.cwd(), "..");
}

export function getAiTasksDir(): string {
  if (isServerlessDeployment()) {
    return join("/tmp", "sjkx-ai-tasks");
  }
  return join(getRepoRoot(), "logs", "ai-tasks");
}

export function getAiTasksStatePath(): string {
  return join(getAiTasksDir(), "state.json");
}

export function getRunnerAvailability(): { available: boolean; message: string | null } {
  if (isServerlessDeployment()) {
    return getRemoteAgentAvailability();
  }

  const repoRoot = getRepoRoot();
  const venvPython = join(repoRoot, ".venv", "bin", "python3");
  const importScript = join(repoRoot, "scripts", "import_to_tables.py");
  const formatScript = join(repoRoot, "scripts", "format_product_fields.py");

  if (!existsSync(importScript) || !existsSync(formatScript)) {
    return {
      available: false,
      message: "未找到 Python 脚本，请在本机仓库根目录启动 web 服务。",
    };
  }

  if (!existsSync(venvPython)) {
    return {
      available: false,
      message: "未找到 .venv，请先在仓库根目录执行 python3 -m venv .venv && pip install -r requirements.txt。",
    };
  }

  return { available: true, message: null };
}

export function shouldUseRemoteAgent(): boolean {
  return isServerlessDeployment() && isRemoteAgentConfigured();
}
