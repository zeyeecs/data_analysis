"use client";

import { Badge } from "@/components/Badge";
import { Button } from "@/components/Button";
import type {
  AiTask,
  AiTaskDefinition,
  AiTaskTable,
  AiTaskType,
  AiTasksSnapshot,
} from "@/lib/ai-tasks/types";
import { cx } from "@/lib/utils";
import { RiCloseLine, RiPlayLine, RiRefreshLine } from "@remixicon/react";
import { format } from "date-fns";
import React from "react";

type ApiResponse = AiTasksSnapshot & {
  availableTypes: AiTaskDefinition[];
  runningLogTail: string | null;
};

function formatTime(value: string | null) {
  if (!value) return "—";
  return format(new Date(value), "yyyy-MM-dd HH:mm:ss");
}

function statusBadge(task: AiTask) {
  switch (task.status) {
    case "pending":
      return <Badge variant="warning">待执行</Badge>;
    case "running":
      return <Badge variant="default">正在执行</Badge>;
    case "completed":
      return <Badge variant="success">已完成</Badge>;
    case "failed":
      return <Badge variant="error">失败</Badge>;
    case "cancelled":
      return <Badge variant="neutral">已取消</Badge>;
    default:
      return <Badge variant="neutral">{task.status}</Badge>;
  }
}

function TaskCard({
  task,
  logTail,
  onCancel,
  compact = false,
}: {
  task: AiTask;
  logTail?: string | null;
  onCancel?: (taskId: string) => void;
  compact?: boolean;
}) {
  return (
    <article className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-medium text-gray-900 dark:text-gray-50">{task.label}</h3>
            {statusBadge(task)}
          </div>
          {!compact ? (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{task.description}</p>
          ) : null}
          <dl className="mt-3 grid gap-1 text-xs text-gray-500 dark:text-gray-400 sm:grid-cols-2">
            <div>
              <dt className="inline">创建：</dt>
              <dd className="inline">{formatTime(task.createdAt)}</dd>
            </div>
            {task.startedAt ? (
              <div>
                <dt className="inline">开始：</dt>
                <dd className="inline">{formatTime(task.startedAt)}</dd>
              </div>
            ) : null}
            {task.finishedAt ? (
              <div>
                <dt className="inline">结束：</dt>
                <dd className="inline">{formatTime(task.finishedAt)}</dd>
              </div>
            ) : null}
            {task.error ? (
              <div className="sm:col-span-2 text-red-600 dark:text-red-400">
                <dt className="inline">错误：</dt>
                <dd className="inline">{task.error}</dd>
              </div>
            ) : null}
          </dl>
        </div>
        {onCancel ? (
          <Button variant="ghost" onClick={() => onCancel(task.id)}>
            <RiCloseLine className="size-4" aria-hidden="true" />
            取消
          </Button>
        ) : null}
      </div>
      {logTail ? (
        <pre className="mt-4 max-h-64 overflow-auto rounded-md border border-gray-200 bg-gray-50 p-3 text-xs leading-relaxed text-gray-700 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-300">
          {logTail}
        </pre>
      ) : null}
    </article>
  );
}

function ManualTaskCard({
  definition,
  disabled,
  submitting,
  onSubmit,
}: {
  definition: AiTaskDefinition;
  disabled: boolean;
  submitting: boolean;
  onSubmit: (type: AiTaskType, table?: AiTaskTable) => void;
}) {
  const [table, setTable] = React.useState<AiTaskTable>("F");

  return (
    <article className="rounded-lg border border-gray-200 p-4 dark:border-gray-800">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-medium text-gray-900 dark:text-gray-50">{definition.label}</h3>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">{definition.description}</p>
        </div>
        <Badge variant="neutral">
          {definition.category === "import"
            ? "导入"
            : definition.category === "llm"
              ? "LLM"
              : "流水线"}
        </Badge>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        {definition.requiresTable ? (
          <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
            竞品表
            <select
              value={table}
              onChange={(event) => setTable(event.target.value as AiTaskTable)}
              className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-900 dark:border-gray-700 dark:bg-gray-950 dark:text-gray-50"
            >
              <option value="F">F</option>
              <option value="R">R</option>
              <option value="V">V</option>
            </select>
          </label>
        ) : null}
        <Button
          variant="secondary"
          disabled={disabled || submitting}
          isLoading={submitting}
          loadingText="加入队列…"
          onClick={() => onSubmit(definition.type, definition.requiresTable ? table : undefined)}
        >
          <RiPlayLine className="size-4" aria-hidden="true" />
          加入队列
        </Button>
      </div>
    </article>
  );
}

export function AiTaskPanel() {
  const [data, setData] = React.useState<ApiResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState<string | null>(null);
  const [submittingType, setSubmittingType] = React.useState<AiTaskType | null>(null);

  const fetchTasks = React.useCallback(async () => {
    try {
      const response = await fetch("/api/ai-tasks", { cache: "no-store" });
      if (!response.ok) {
        throw new Error("加载任务列表失败");
      }
      const payload = (await response.json()) as ApiResponse;
      setData(payload);
      setError(null);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    void fetchTasks();
    const timer = window.setInterval(() => {
      void fetchTasks();
    }, 4000);
    return () => window.clearInterval(timer);
  }, [fetchTasks]);

  const enqueueTask = async (type: AiTaskType, table?: AiTaskTable) => {
    setSubmittingType(type);
    setError(null);
    try {
      const response = await fetch("/api/ai-tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type,
          params: table ? { table } : {},
        }),
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? "创建任务失败");
      }
      await fetchTasks();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "创建任务失败");
    } finally {
      setSubmittingType(null);
    }
  };

  const cancelTask = async (taskId: string) => {
    setError(null);
    try {
      const response = await fetch(`/api/ai-tasks?id=${encodeURIComponent(taskId)}`, {
        method: "DELETE",
      });
      const payload = (await response.json()) as { error?: string };
      if (!response.ok) {
        throw new Error(payload.error ?? "取消任务失败");
      }
      await fetchTasks();
    } catch (cancelError) {
      setError(cancelError instanceof Error ? cancelError.message : "取消任务失败");
    }
  };

  const runnerDisabled = !data?.runnerAvailable;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-gray-900 sm:text-xl dark:text-gray-50">
            AI 任务管理
          </h1>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            手动触发导入、LLM 分类等后台任务。任务按队列顺序执行，同时仅运行一个任务。
          </p>
        </div>
        <Button variant="secondary" onClick={() => void fetchTasks()}>
          <RiRefreshLine className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {data && !data.runnerAvailable ? (
        <div className="rounded-lg border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900 dark:border-yellow-700/40 dark:bg-yellow-400/10 dark:text-yellow-200">
          {data.runnerMessage ?? "当前环境无法执行任务，仅可查看历史记录。"}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-red-300 bg-red-50 p-4 text-sm text-red-700 dark:border-red-700/40 dark:bg-red-400/10 dark:text-red-300">
          {error}
        </div>
      ) : null}

      <section className="space-y-4">
        <div>
          <h2 className="font-medium text-gray-900 dark:text-gray-50">手动执行</h2>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            选择任务类型加入队列，系统将自动按顺序执行。
          </p>
        </div>
        <div className="grid gap-4 xl:grid-cols-2">
          {(data?.availableTypes ?? []).map((definition) => (
            <ManualTaskCard
              key={definition.type}
              definition={definition}
              disabled={runnerDisabled}
              submitting={submittingType === definition.type}
              onSubmit={enqueueTask}
            />
          ))}
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="font-medium text-gray-900 dark:text-gray-50">正在执行</h2>
          {data?.running ? <Badge variant="default">1</Badge> : <Badge variant="neutral">0</Badge>}
        </div>
        {loading && !data ? (
          <p className="text-sm text-gray-500">加载中…</p>
        ) : data?.running ? (
          <TaskCard task={data.running} logTail={data.runningLogTail} />
        ) : (
          <div
            className={cx(
              "rounded-lg border border-dashed border-gray-300 p-6 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400",
            )}
          >
            当前没有正在执行的任务。
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <h2 className="font-medium text-gray-900 dark:text-gray-50">待执行</h2>
          <Badge variant="warning">{data?.pending.length ?? 0}</Badge>
        </div>
        {data?.pending.length ? (
          <div className="space-y-3">
            {data.pending.map((task, index) => (
              <div key={task.id} className="relative">
                <div className="absolute -left-1 top-4 hidden h-8 w-1 rounded-full bg-yellow-400 sm:block" />
                <TaskCard
                  task={task}
                  compact
                  onCancel={runnerDisabled ? undefined : cancelTask}
                />
                {index === 0 && data.running ? (
                  <p className="mt-2 text-xs text-gray-400">下一项将在当前任务完成后自动开始。</p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-gray-300 p-6 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
            队列为空。可在上方手动加入导入或 LLM 分类任务。
          </div>
        )}
      </section>

      {data?.recent.length ? (
        <section className="space-y-4">
          <h2 className="font-medium text-gray-900 dark:text-gray-50">最近完成</h2>
          <div className="space-y-3">
            {data.recent.map((task) => (
              <TaskCard key={task.id} task={task} compact />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
