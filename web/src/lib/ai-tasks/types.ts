export type AiTaskStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export type AiTaskType =
  | "import-incremental"
  | "import-reimport"
  | "import-table"
  | "llm-format-full"
  | "llm-format-reconcile"
  | "pipeline";

export type AiTaskTable = "F" | "R" | "V";

export type AiTaskParams = {
  table?: AiTaskTable;
};

export type AiTask = {
  id: string;
  type: AiTaskType;
  label: string;
  description: string;
  params: AiTaskParams;
  status: AiTaskStatus;
  createdAt: string;
  startedAt: string | null;
  finishedAt: string | null;
  logFile: string | null;
  exitCode: number | null;
  error: string | null;
};

export type AiTaskDefinition = {
  type: AiTaskType;
  label: string;
  description: string;
  category: "import" | "llm" | "pipeline";
  requiresTable?: boolean;
};

export type AiTasksSnapshot = {
  pending: AiTask[];
  running: AiTask | null;
  recent: AiTask[];
  runnerAvailable: boolean;
  runnerMessage: string | null;
};
