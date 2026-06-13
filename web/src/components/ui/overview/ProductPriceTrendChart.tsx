"use client";

import { LineChart } from "@/components/LineChart";
import type { ProductTrendPoint } from "@/data/schema";
import { formatters } from "@/lib/utils";
import { formatDate, interval, isWithinInterval } from "date-fns";
import { DateRange } from "react-day-picker";

type ProductPriceTrendChartProps = {
  trend: ProductTrendPoint[];
  selectedDates: DateRange | undefined;
};

const priceFormatter = (value: number) => formatters.currency(value, "CNY");

export function ProductPriceTrendChart({ trend, selectedDates }: ProductPriceTrendChartProps) {
  const selectedDatesInterval =
    selectedDates?.from && selectedDates?.to
      ? interval(selectedDates.from, selectedDates.to)
      : null;

  const chartData = trend
    .filter((row) => {
      if (!selectedDatesInterval) return true;
      return isWithinInterval(new Date(row.date), selectedDatesInterval);
    })
    .map((row) => {
      const tooltipExtras: Record<string, string> = {};
      if (row.minPriceProducts) tooltipExtras["最低价"] = row.minPriceProducts;
      if (row.maxPriceProducts) tooltipExtras["最高价"] = row.maxPriceProducts;
      return {
        formattedDate: formatDate(new Date(row.date), "MM/dd"),
        均价: row.avgPrice ?? 0,
        最低价: row.minPrice ?? 0,
        最高价: row.maxPrice ?? 0,
        tooltipExtras,
      };
    });

  if (chartData.length === 0) {
    return (
      <p className="mt-6 text-sm text-gray-500 dark:text-gray-400">该区间内无价格数据</p>
    );
  }

  return (
    <LineChart
      className="mt-6 h-72"
      data={chartData}
      index="formattedDate"
      colors={["indigo", "emerald", "pink"]}
      valueFormatter={(value) => priceFormatter(value as number)}
      categories={["均价", "最低价", "最高价"]}
      showLegend
      showYAxis
      showTooltip
      autoMinValue
      connectNulls
    />
  );
}
