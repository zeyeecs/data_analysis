"use client";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/Popover";
import { cx } from "@/lib/utils";
import { RiArrowDownSLine, RiCheckLine } from "@remixicon/react";
import React from "react";

type MultiSelectDropdownProps = {
  options: string[];
  selected: string[];
  onSelectedChange: (values: string[]) => void;
  excluded?: string[];
  onExcludedChange?: (values: string[]) => void;
  emptyLabel?: string;
  placeholder?: string;
  className?: string;
};

export function multiSelectTriggerLabel(
  selected: string[],
  emptyLabel = "全部",
  excluded?: string[],
): string {
  const exc = excluded ?? [];
  if (selected.length === 0 && exc.length === 0) return emptyLabel;
  if (selected.length > 0 && exc.length === 0) {
    if (selected.length === 1) return selected[0];
    return `已选 ${selected.length} 项`;
  }
  if (selected.length === 0 && exc.length > 0) {
    if (exc.length === 1) return `排除 ${exc[0]}`;
    return `排除 ${exc.length} 项`;
  }
  return `含 ${selected.length} · 排 ${exc.length}`;
}

function ExcludeSlashIcon({ active }: { active: boolean }) {
  return (
    <span
      className={cx(
        "relative flex size-4 shrink-0 items-center justify-center rounded border",
        active
          ? "border-red-500 bg-red-50 dark:border-red-400 dark:bg-red-950/50"
          : "border-gray-300 bg-white dark:border-gray-600 dark:bg-gray-950",
      )}
      aria-hidden
    >
      <span
        className={cx(
          "block h-[10px] w-[1.5px] rotate-45 rounded-full",
          active ? "bg-red-500 dark:bg-red-400" : "bg-gray-400 dark:bg-gray-500",
        )}
      />
    </span>
  );
}

export function MultiSelectDropdown({
  options,
  selected,
  onSelectedChange,
  excluded,
  onExcludedChange,
  emptyLabel = "全部",
  placeholder = "先搜索以加载选项",
  className,
}: MultiSelectDropdownProps) {
  const [open, setOpen] = React.useState(false);
  const excludeEnabled = onExcludedChange != null;
  const excludedValues = excluded ?? [];

  const toggleInclude = (value: string) => {
    if (selected.includes(value)) {
      onSelectedChange(selected.filter((item) => item !== value));
      return;
    }
    onSelectedChange([...selected, value]);
    if (excludeEnabled && excludedValues.includes(value)) {
      onExcludedChange!(excludedValues.filter((item) => item !== value));
    }
  };

  const toggleExclude = (value: string) => {
    if (!excludeEnabled) return;
    if (excludedValues.includes(value)) {
      onExcludedChange!(excludedValues.filter((item) => item !== value));
      return;
    }
    onExcludedChange!([...excludedValues, value]);
    if (selected.includes(value)) {
      onSelectedChange(selected.filter((item) => item !== value));
    }
  };

  const clearAll = () => {
    onSelectedChange([]);
    if (excludeEnabled) onExcludedChange!([]);
  };

  const hasSelection = selected.length > 0 || excludedValues.length > 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={cx(
            "group/trigger flex h-9 w-full select-none items-center justify-between gap-2 truncate rounded-md border px-2.5 py-1.5 shadow outline-none transition sm:text-sm",
            "border-gray-400 dark:border-gray-600",
            "text-gray-900 dark:text-gray-50",
            "bg-white dark:bg-gray-800",
            "hover:bg-gray-50 hover:dark:bg-gray-700",
            "focus-visible:ring-2 focus-visible:ring-indigo-300 focus-visible:dark:ring-indigo-600/50",
            hasSelection &&
              "border-indigo-300 bg-indigo-50/80 dark:border-indigo-700 dark:bg-indigo-950/40",
            className,
          )}
        >
          <span className="truncate">
            {multiSelectTriggerLabel(selected, emptyLabel, excludedValues)}
          </span>
          <RiArrowDownSLine
            className={cx(
              "size-4 shrink-0 text-gray-400 transition-transform",
              open && "rotate-180",
            )}
            aria-hidden="true"
          />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        sideOffset={4}
        collisionPadding={12}
        className={cx(
          "p-0",
          excludeEnabled
            ? "w-[var(--radix-popover-trigger-width)] min-w-[12rem]"
            : "w-[var(--radix-popover-trigger-width)] min-w-[10rem]",
        )}
        onOpenAutoFocus={(event) => event.preventDefault()}
      >
        {options.length === 0 ? (
          <p className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400">{placeholder}</p>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2 border-b border-gray-200 px-3 py-2 dark:border-gray-800">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {excludeEnabled ? "左含 · 右排 · 匹配任一" : "可多选 · 匹配任一"}
              </span>
              {hasSelection ? (
                <button
                  type="button"
                  className="text-xs font-medium text-indigo-600 hover:text-indigo-500 dark:text-indigo-400"
                  onClick={clearAll}
                >
                  清空
                </button>
              ) : null}
            </div>
            <ul className="max-h-64 overflow-y-auto py-1" role="listbox" aria-multiselectable>
              {options.map((option) => {
                const included = selected.includes(option);
                const excludedActive = excludedValues.includes(option);
                return (
                  <li
                    key={option}
                    role="presentation"
                    className={cx(
                      "flex items-center gap-1 px-2 py-0.5 transition",
                      (included || excludedActive) && "bg-gray-50 dark:bg-gray-900/60",
                    )}
                  >
                    <button
                      type="button"
                      aria-label={`包含 ${option}`}
                      className={cx(
                        "flex shrink-0 items-center justify-center rounded p-1.5 transition",
                        "hover:bg-gray-100 dark:hover:bg-gray-900",
                      )}
                      onClick={() => toggleInclude(option)}
                    >
                      <span
                        className={cx(
                          "flex size-4 items-center justify-center rounded border",
                          included
                            ? "border-indigo-500 bg-indigo-500 text-white dark:border-indigo-400 dark:bg-indigo-500"
                            : "border-gray-300 bg-white dark:border-gray-600 dark:bg-gray-950",
                        )}
                      >
                        {included ? <RiCheckLine className="size-3" /> : null}
                      </span>
                    </button>
                    <span className="min-w-0 flex-1 truncate px-0.5 text-sm text-gray-900 dark:text-gray-50">
                      {option}
                    </span>
                    {excludeEnabled ? (
                      <button
                        type="button"
                        aria-label={`排除 ${option}`}
                        className={cx(
                          "flex shrink-0 items-center justify-center rounded p-1.5 transition",
                          "hover:bg-gray-100 dark:hover:bg-gray-900",
                        )}
                        onClick={() => toggleExclude(option)}
                      >
                        <ExcludeSlashIcon active={excludedActive} />
                      </button>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}
