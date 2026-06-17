import { spawn, type ChildProcess } from "node:child_process";
import { createWriteStream, existsSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import { getRepoRoot, getRunnerAvailability } from "@/lib/ai-tasks/paths";
import {
  finalizeTask,
  getNextPendingTask,
  getRunningTaskId,
  getTaskById,
  markTaskRunning,
  setRunningTaskId,
} from "@/lib/ai-tasks/store";
import type { AiTask, AiTaskParams, AiTaskType } from "@/lib/ai-tasks/types";

type ActiveProcess = {
  taskId: string;
  process: ChildProcess;
};

declare global {
  // eslint-disable-next-line no-var
  var __sjkxAiTaskProcess: ActiveProcess | undefined;
}

function getActiveProcess(): ActiveProcess | null {
  return globalThis.__sjkxAiTaskProcess ?? null;
}

function setActiveProcess(value: ActiveProcess | null) {
  globalThis.__sjkxAiTaskProcess = value ?? undefined;
}

function buildCommand(type: AiTaskType, params: AiTaskParams): { command: string; args: string[] } {
  const repoRoot = getRepoRoot();
  const python = join(repoRoot, ".venv", "bin", "python3");

  switch (type) {
    case "import-incremental":
      return {
        command: python,
        args: [
          "-u",
          "scripts/import_to_tables.py",
          "--category",
          "F",
          "--category",
          "R",
          "--category",
          "V",
        ],
      };
    case "import-reimport":
      return {
        command: python,
        args: [
          "-u",
          "scripts/import_to_tables.py",
          "--reimport-all",
          "--category",
          "F",
          "--category",
          "R",
          "--category",
          "V",
        ],
      };
    case "import-table":
      return {
        command: python,
        args: ["-u", "scripts/import_to_tables.py", "--category", params.table ?? "F"],
      };
    case "llm-format-full":
      return {
        command: python,
        args: ["-u", "scripts/format_product_fields.py", "--write-db"],
      };
    case "llm-format-reconcile":
      return {
        command: python,
        args: ["-u", "scripts/format_product_fields.py", "--write-db", "--only-list-brand"],
      };
    case "pipeline":
      return {
        command: "bash",
        args: ["scripts/run_server_pipeline.sh"],
      };
    default: {
      const _exhaustive: never = type;
      throw new Error(`未支持的任务类型: ${_exhaustive}`);
    }
  }
}

function startTask(task: AiTask) {
  const repoRoot = getRepoRoot();
  const logDir = join(repoRoot, "logs", "ai-tasks");
  mkdirSync(logDir, { recursive: true });
  const logFile = join(logDir, `${task.id}.log`);
  const logStream = createWriteStream(logFile, { flags: "a" });
  const { command, args } = buildCommand(task.type, task.params);

  logStream.write(`=== ${new Date().toISOString()} start ${task.label} ===\n`);
  logStream.write(`command: ${command} ${args.join(" ")}\n\n`);

  const child = spawn(command, args, {
    cwd: repoRoot,
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
  });

  markTaskRunning(task.id, logFile);
  setActiveProcess({ taskId: task.id, process: child });

  child.stdout.on("data", (chunk: Buffer) => {
    logStream.write(chunk);
  });
  child.stderr.on("data", (chunk: Buffer) => {
    logStream.write(chunk);
  });

  child.on("close", (code) => {
    logStream.write(`\n=== ${new Date().toISOString()} exit ${code ?? "null"} ===\n`);
    logStream.end();
    setActiveProcess(null);

    if (code === 0) {
      finalizeTask(task.id, "completed", code, null);
    } else {
      finalizeTask(
        task.id,
        "failed",
        code,
        code === null ? "进程异常退出" : `退出码 ${code}`,
      );
    }

    void drainQueue();
  });

  child.on("error", (error) => {
    logStream.write(`\n=== spawn error: ${error.message} ===\n`);
    logStream.end();
    setActiveProcess(null);
    finalizeTask(task.id, "failed", null, error.message);
    void drainQueue();
  });
}

export async function drainQueue() {
  const availability = getRunnerAvailability();
  if (!availability.available) return;

  syncRunningProcess();

  const runningId = getRunningTaskId();
  const active = getActiveProcess();
  if (runningId && !active) {
    const runningTask = getTaskById(runningId);
    if (runningTask?.status === "running") {
      finalizeTask(runningId, "failed", null, "服务重启导致任务中断");
    } else {
      setRunningTaskId(null);
    }
  }

  if (getRunningTaskId() || getActiveProcess()) return;

  const next = getNextPendingTask();
  if (!next) return;

  startTask(next);
}

export function syncRunningProcess() {
  const active = getActiveProcess();
  if (!active) return;

  if (active.process.exitCode !== null || active.process.killed) {
    setActiveProcess(null);
  }
}

export function readTaskLogTail(logFile: string | null, maxLines = 80): string | null {
  if (!logFile || !existsSync(logFile)) return null;
  const content = readFileSync(logFile, "utf8");
  const lines = content.split("\n");
  if (lines.length <= maxLines) return content.trimEnd();
  return lines.slice(-maxLines).join("\n").trimEnd();
}
