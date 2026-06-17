import { NextRequest, NextResponse } from "next/server";

import { AI_TASK_DEFINITIONS } from "@/lib/ai-tasks/definitions";
import { getRunnerAvailability, shouldUseRemoteAgent } from "@/lib/ai-tasks/paths";
import {
  proxyRemoteAgentDelete,
  proxyRemoteAgentGet,
  proxyRemoteAgentPost,
} from "@/lib/ai-tasks/remote-agent";
import { drainQueue, readTaskLogTail, syncRunningProcess } from "@/lib/ai-tasks/runner";
import { cancelPendingTask, createTask, listTasksSnapshot } from "@/lib/ai-tasks/store";
import type { AiTaskParams, AiTaskTable, AiTaskType } from "@/lib/ai-tasks/types";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const TASK_TYPES = new Set<AiTaskType>([
  "import-incremental",
  "import-reimport",
  "import-table",
  "llm-format-full",
  "llm-format-reconcile",
  "pipeline",
]);

const TASK_TABLES = new Set<AiTaskTable>(["F", "R", "V"]);

function isTaskType(value: unknown): value is AiTaskType {
  return typeof value === "string" && TASK_TYPES.has(value as AiTaskType);
}

function isTaskTable(value: unknown): value is AiTaskTable {
  return typeof value === "string" && TASK_TABLES.has(value as AiTaskTable);
}

function jsonFromProxy(response: Response, payload: unknown) {
  return NextResponse.json(payload, { status: response.status });
}

export async function GET() {
  try {
    if (shouldUseRemoteAgent()) {
      const { response, payload } = await proxyRemoteAgentGet();
      return jsonFromProxy(response, payload);
    }

    syncRunningProcess();
    await drainQueue();

    const availability = getRunnerAvailability();
    const snapshot = listTasksSnapshot();

    return NextResponse.json({
      ...snapshot,
      availableTypes: AI_TASK_DEFINITIONS,
      runnerAvailable: availability.available,
      runnerMessage: availability.message,
      runningLogTail: snapshot.running
        ? readTaskLogTail(snapshot.running.logFile)
        : null,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "加载任务失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  const availability = getRunnerAvailability();
  if (!availability.available) {
    return NextResponse.json(
      { error: availability.message ?? "当前环境无法执行任务" },
      { status: 503 },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "请求体必须是 JSON" }, { status: 400 });
  }

  const payload = body as { type?: unknown; params?: AiTaskParams };
  if (!isTaskType(payload.type)) {
    return NextResponse.json({ error: "无效的任务类型" }, { status: 400 });
  }

  const params: AiTaskParams = {};
  if (payload.params?.table !== undefined) {
    if (!isTaskTable(payload.params.table)) {
      return NextResponse.json({ error: "table 必须是 F / R / V" }, { status: 400 });
    }
    params.table = payload.params.table;
  }

  try {
    if (shouldUseRemoteAgent()) {
      const { response, payload: remotePayload } = await proxyRemoteAgentPost(
        payload.type,
        params,
      );
      return jsonFromProxy(response, remotePayload);
    }

    const task = createTask(payload.type, params);
    await drainQueue();
    return NextResponse.json({ task }, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "创建任务失败";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}

export async function DELETE(request: NextRequest) {
  const taskId = request.nextUrl.searchParams.get("id");
  if (!taskId) {
    return NextResponse.json({ error: "缺少任务 id" }, { status: 400 });
  }

  try {
    if (shouldUseRemoteAgent()) {
      const { response, payload } = await proxyRemoteAgentDelete(taskId);
      return jsonFromProxy(response, payload);
    }

    const cancelled = cancelPendingTask(taskId);
    if (!cancelled) {
      return NextResponse.json({ error: "任务不存在或无法取消" }, { status: 404 });
    }

    return NextResponse.json({ task: cancelled });
  } catch (error) {
    const message = error instanceof Error ? error.message : "取消任务失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
