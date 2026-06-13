"use client";

import React from "react";

import { Button } from "@/components/Button";
import { DateRangePicker, type DateRangePreset } from "@/components/DatePicker";
import { Input } from "@/components/Input";
import { Label } from "@/components/Label";
import { MultiSelectDropdown } from "@/components/ui/overview/MultiSelectDropdown";
import {
  buildRecentDayRange,
  isSameDateRange,
  RECENT_DAY_SHORTCUTS,
} from "@/lib/dates";
import { cx } from "@/lib/utils";
import type { AttributeFilterSelection, FilterOptions } from "@/data/schema";
import { DateRange } from "react-day-picker";

const SHOP_OPTIONS = ["F", "R", "V"];

type ProductSearchBarProps = {
  keywords: string;
  colorFilter: AttributeFilterSelection;
  conditionFilter: AttributeFilterSelection;
  materialFilter: AttributeFilterSelection;
  yearFilter: AttributeFilterSelection;
  shops: string[];
  selectedDates: DateRange | undefined;
  filterOptions: FilterOptions;
  analyzing: boolean;
  minDate?: Date;
  maxDate?: Date;
  onKeywordsChange: (value: string) => void;
  onColorFilterChange: (value: AttributeFilterSelection) => void;
  onConditionFilterChange: (value: AttributeFilterSelection) => void;
  onMaterialFilterChange: (value: AttributeFilterSelection) => void;
  onYearFilterChange: (value: AttributeFilterSelection) => void;
  onShopsChange: (value: string[]) => void;
  onDatesChange: (dates: DateRange | undefined) => void;
  onAnalyze: () => void;
};

function Field({
  label,
  className,
  children,
  compact = false,
}: {
  label: string;
  className?: string;
  children: React.ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={className}>
      <Label
        className={cx(
          "block font-medium text-gray-500 dark:text-gray-400",
          compact ? "mb-1 text-[11px]" : "mb-1.5 text-xs",
        )}
      >
        {label}
      </Label>
      {children}
    </div>
  );
}

export function ProductSearchBar(props: ProductSearchBarProps) {
  const {
    keywords,
    colorFilter,
    conditionFilter,
    materialFilter,
    yearFilter,
    shops,
    selectedDates,
    filterOptions,
    analyzing,
    minDate,
    maxDate,
    onKeywordsChange,
    onColorFilterChange,
    onConditionFilterChange,
    onMaterialFilterChange,
    onYearFilterChange,
    onShopsChange,
    onDatesChange,
    onAnalyze,
  } = props;

  const rangeOpts = { minDate, maxDate };

  const datePresets = React.useMemo<DateRangePreset[]>(
    () =>
      RECENT_DAY_SHORTCUTS.map((days) => ({
        label: `最近 ${days} 天`,
        dateRange: buildRecentDayRange(days, rangeOpts),
      })),
    [minDate, maxDate],
  );

  const filterFields = [
    {
      key: "shops",
      label: "数据来源",
      options: SHOP_OPTIONS,
      selected: shops,
      onChange: onShopsChange,
      emptyLabel: "F / R / V",
      placeholder: "暂无选项",
      excludeEnabled: false,
    },
    {
      key: "colors",
      label: "颜色",
      options: filterOptions.colors,
      selection: colorFilter,
      onChange: onColorFilterChange,
      placeholder: "先分析以加载",
      excludeEnabled: true,
    },
    {
      key: "conditions",
      label: "品相",
      options: filterOptions.conditions,
      selection: conditionFilter,
      onChange: onConditionFilterChange,
      placeholder: "先分析以加载",
      excludeEnabled: true,
    },
    {
      key: "materials",
      label: "材质",
      options: filterOptions.materials,
      selection: materialFilter,
      onChange: onMaterialFilterChange,
      placeholder: "先分析以加载",
      excludeEnabled: true,
    },
    {
      key: "years",
      label: "年份",
      options: filterOptions.years,
      selection: yearFilter,
      onChange: onYearFilterChange,
      placeholder: "先分析以加载",
      excludeEnabled: true,
    },
  ] as const;

  return (
    <div className="flex w-full flex-col gap-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field label="关键词搜索" className="min-w-0 flex-1">
          <Input
            type="search"
            placeholder="留空分析全部；多个关键词用空格或逗号分隔"
            value={keywords}
            onChange={(e) => onKeywordsChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onAnalyze();
            }}
          />
        </Field>
        <Button
          variant="primary"
          className="h-9 w-full shrink-0 sm:w-auto sm:min-w-[6.5rem]"
          isLoading={analyzing}
          loadingText="分析中…"
          onClick={onAnalyze}
        >
          开始分析
        </Button>
      </div>

      <div className="rounded-lg border border-gray-200 bg-gray-50/70 p-3 dark:border-gray-800 dark:bg-gray-900/35">
        <div className="grid grid-cols-2 gap-x-3 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
          {filterFields.map((field) => (
            <Field key={field.key} label={field.label} compact>
              {field.excludeEnabled ? (
                <MultiSelectDropdown
                  options={field.options}
                  selected={field.selection.include}
                  onSelectedChange={(include) =>
                    field.onChange({ include, exclude: field.selection.exclude })
                  }
                  excluded={field.selection.exclude}
                  onExcludedChange={(exclude) =>
                    field.onChange({ include: field.selection.include, exclude })
                  }
                  placeholder={field.placeholder}
                />
              ) : (
                <MultiSelectDropdown
                  options={field.options}
                  selected={field.selected}
                  onSelectedChange={field.onChange}
                  emptyLabel={"emptyLabel" in field ? field.emptyLabel : undefined}
                  placeholder={field.placeholder}
                />
              )}
            </Field>
          ))}
        </div>
      </div>

      <Field label="日期范围">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:gap-3">
          <div className="flex flex-wrap gap-1.5">
            {RECENT_DAY_SHORTCUTS.map((days) => {
              const range = buildRecentDayRange(days, rangeOpts);
              const active = isSameDateRange(selectedDates, range);
              return (
                <Button
                  key={days}
                  type="button"
                  variant={active ? "primary" : "secondary"}
                  className={cx(
                    "h-8 px-2.5 text-xs shadow-none",
                    active && "ring-1 ring-indigo-500/40",
                  )}
                  onClick={() => onDatesChange(range)}
                >
                  {days}天
                </Button>
              );
            })}
          </div>
          <DateRangePicker
            value={selectedDates}
            onChange={onDatesChange}
            className="w-full lg:w-auto"
            toDate={maxDate}
            fromDate={minDate}
            presets={datePresets}
            align="start"
          />
        </div>
      </Field>
    </div>
  );
}
