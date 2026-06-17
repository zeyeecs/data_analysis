from __future__ import annotations

from typing import Any

TASK_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "import-incremental",
        "label": "增量导入新数据",
        "description": "从飞书云盘增量导入 F / R / V 新 snapshot（默认跳过已有日期）",
        "category": "import",
    },
    {
        "type": "import-reimport",
        "label": "全量重新导入",
        "description": "导入飞书目录全部 xlsx，并对已有 snapshot_date 按日覆盖",
        "category": "import",
    },
    {
        "type": "import-table",
        "label": "单表导入",
        "description": "只导入指定竞品表（F / R / V）",
        "category": "import",
        "requiresTable": True,
    },
    {
        "type": "llm-format-full",
        "label": "LLM 全量分类",
        "description": "对 F / R / V 全表做型号拆分与 LLM 语义解析（耗时较长）",
        "category": "llm",
    },
    {
        "type": "llm-format-reconcile",
        "label": "LLM 增量归一化",
        "description": "仅处理 brand 为列表字面量（如 ['Hermes']）的行",
        "category": "llm",
    },
    {
        "type": "pipeline",
        "label": "完整流水线",
        "description": "增量导入 F / R / V + brand reconcile，等同每日定时任务",
        "category": "pipeline",
    },
]

DEFINITION_BY_TYPE = {item["type"]: item for item in TASK_DEFINITIONS}


def build_task_label(task_type: str, params: dict[str, Any]) -> str:
    definition = DEFINITION_BY_TYPE[task_type]
    table = params.get("table")
    if task_type == "import-table" and table:
        return f"{definition['label']} · {table}"
    return definition["label"]
