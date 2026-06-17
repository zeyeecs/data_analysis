import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { randomUUID } from "node:crypto";

import { buildTaskLabel, getTaskDefinition } from "@/lib/ai-tasks/definitions";
import { getAiTasksDir, getAiTasksStatePath, isServerlessDeployment } from "@/lib/ai-tasks/paths";
import type { AiTask, AiTaskParams, AiTaskStatus, AiTaskType } from "@/lib/ai-tasks/types";

type TaskStoreState = {
  tasks: AiTask[];
  runningTaskId: string | null;
};

const MAX_RECENT_TASKS = 20;

function emptySnapshot() {
  return { pending: [] as AiTask[], running: null as AiTask | null, recent: [] as AiTask[] };
}

function emptyState(): TaskStoreState {
  return { tasks: [], runningTaskId: null };
}

function ensureStoreDir() {
  if (isServerlessDeployment()) return;
  mkdirSync(getAiTasksDir(), { recursive: true });
}

function readState(): TaskStoreState {
  if (isServerlessDeployment()) {
    return emptyState();
  }
  ensureStoreDir();
  const path = getAiTasksStatePath();
  if (!existsSync(path)) {
    return emptyState();
  }
  try {
    const raw = readFileSync(path, "utf8");
    const parsed = JSON.parse(raw) as TaskStoreState;
    if (!Array.isArray(parsed.tasks)) {
      return emptyState();
    }
    return {
      tasks: parsed.tasks,
      runningTaskId: parsed.runningTaskId ?? null,
    };
  } catch {
    return emptyState();
  }
}

function writeState(state: TaskStoreState) {
  if (isServerlessDeployment()) return;
  ensureStoreDir();
  const path = getAiTasksStatePath();
  const tempPath = `${path}.tmp`;
  writeFileSync(tempPath, JSON.stringify(state, null, 2), "utf8");
  renameSync(tempPath, path);
}

function mutateState(mutator: (state: TaskStoreState) => void): TaskStoreState {
  const state = readState();
  mutator(state);
  writeState(state);
  return state;
}

export function createTask(type: AiTaskType, params: AiTaskParams = {}): AiTask {
  if (isServerlessDeployment()) {
    throw new Error("Vercel 上无法创建任务");
  }

  const definition = getTaskDefinition(type);
  if (definition.requiresTable && !params.table) {
    throw new Error("该任务需要指定竞品表（F / R / V）");
  }

  const task: AiTask = {
    id: randomUUID(),
    type,
    label: buildTaskLabel(type, params),
    description: definition.description,
    params,
    status: "pending",
    createdAt: new Date().toISOString(),
    startedAt: null,
    finishedAt: null,
    logFile: null,
    exitCode: null,
    error: null,
  };

  mutateState((state) => {
    state.tasks.unshift(task);
  });

  return task;
}

export function getTaskById(taskId: string): AiTask | null {
  const state = readState();
  return state.tasks.find((task) => task.id === taskId) ?? null;
}

export function updateTask(taskId: string, patch: Partial<AiTask>): AiTask | null {
  let updated: AiTask | null = null;
  mutateState((state) => {
    const index = state.tasks.findIndex((task) => task.id === taskId);
    if (index === -1) return;
    updated = { ...state.tasks[index], ...patch };
    state.tasks[index] = updated;
  });
  return updated;
}

export function setRunningTaskId(taskId: string | null) {
  mutateState((state) => {
    state.runningTaskId = taskId;
  });
}

export function getRunningTaskId(): string | null {
  return readState().runningTaskId;
}

export function cancelPendingTask(taskId: string): AiTask | null {
  let cancelled: AiTask | null = null;
  mutateState((state) => {
    const index = state.tasks.findIndex((task) => task.id === taskId);
    if (index === -1) return;
    const task = state.tasks[index];
    if (task.status !== "pending") return;
    cancelled = {
      ...task,
      status: "cancelled",
      finishedAt: new Date().toISOString(),
    };
    state.tasks[index] = cancelled;
  });
  return cancelled;
}

export function finalizeTask(
  taskId: string,
  status: Extract<AiTaskStatus, "completed" | "failed">,
  exitCode: number | null,
  error: string | null,
): AiTask | null {
  let finalized: AiTask | null = null;
  mutateState((state) => {
    if (state.runningTaskId === taskId) {
      state.runningTaskId = null;
    }
    const index = state.tasks.findIndex((task) => task.id === taskId);
    if (index === -1) return;
    finalized = {
      ...state.tasks[index],
      status,
      finishedAt: new Date().toISOString(),
      exitCode,
      error,
    };
    state.tasks[index] = finalized;
  });
  return finalized;
}

export function listTasksSnapshot() {
  if (isServerlessDeployment()) {
    return emptySnapshot();
  }

  const state = readState();
  const pending = state.tasks.filter((task) => task.status === "pending");
  const running =
    state.tasks.find((task) => task.id === state.runningTaskId && task.status === "running") ??
    state.tasks.find((task) => task.status === "running") ??
    null;
  const recent = state.tasks
    .filter((task) => ["completed", "failed", "cancelled"].includes(task.status))
    .slice(0, MAX_RECENT_TASKS);

  return { pending, running, recent };
}

export function getNextPendingTask(): AiTask | null {
  const state = readState();
  return state.tasks.find((task) => task.status === "pending") ?? null;
}

export function markTaskRunning(taskId: string, logFile: string): AiTask | null {
  let running: AiTask | null = null;
  mutateState((state) => {
    const index = state.tasks.findIndex((task) => task.id === taskId);
    if (index === -1) return;
    running = {
      ...state.tasks[index],
      status: "running",
      startedAt: new Date().toISOString(),
      logFile,
      exitCode: null,
      error: null,
    };
    state.tasks[index] = running;
    state.runningTaskId = taskId;
  });
  return running;
}
