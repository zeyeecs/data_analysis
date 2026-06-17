import type { AiTaskDefinition, AiTaskParams, AiTaskType } from "@/lib/ai-tasks/types";

export const AI_TASK_DEFINITIONS: AiTaskDefinition[] = [
  {
    type: "import-incremental",
    label: "增量导入新数据",
    description: "从飞书云盘增量导入 F / R / V 新 snapshot（默认跳过已有日期）",
    category: "import",
  },
  {
    type: "import-reimport",
    label: "全量重新导入",
    description: "导入飞书目录全部 xlsx，并对已有 snapshot_date 按日覆盖",
    category: "import",
  },
  {
    type: "import-table",
    label: "单表导入",
    description: "只导入指定竞品表（F / R / V）",
    category: "import",
    requiresTable: true,
  },
  {
    type: "llm-format-full",
    label: "LLM 全量分类",
    description: "对 F / R / V 全表做型号拆分与 LLM 语义解析（耗时较长）",
    category: "llm",
  },
  {
    type: "llm-format-reconcile",
    label: "LLM 增量归一化",
    description: "仅处理 brand 为列表字面量（如 ['Hermes']）的行",
    category: "llm",
  },
  {
    type: "pipeline",
    label: "完整流水线",
    description: "增量导入 F / R / V + brand reconcile，等同每日定时任务",
    category: "pipeline",
  },
];

const definitionByType = new Map(AI_TASK_DEFINITIONS.map((item) => [item.type, item]));

export function getTaskDefinition(type: AiTaskType): AiTaskDefinition {
  const definition = definitionByType.get(type);
  if (!definition) {
    throw new Error(`未知任务类型: ${type}`);
  }
  return definition;
}

export function buildTaskLabel(type: AiTaskType, params: AiTaskParams): string {
  const definition = getTaskDefinition(type);
  if (type === "import-table" && params.table) {
    return `${definition.label} · ${params.table}`;
  }
  return definition.label;
}
