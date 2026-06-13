"use client";

import React from "react";

import type { FilterOptions, ProductAnalysis, ShopTotals } from "@/data/schema";

export type ProductQuery = {
  q: string;
  colors: string[];
  excludeColors: string[];
  conditions: string[];
  excludeConditions: string[];
  materials: string[];
  excludeMaterials: string[];
  years: string[];
  excludeYears: string[];
  shops: string[];
  start: string;
  end: string;
  brand?: string;
  product?: string;
};

type OverviewContextValue = {
  analysis: ProductAnalysis | null;
  filterOptions: FilterOptions;
  shops: ShopTotals | null;
  loading: boolean;
  analyzing: boolean;
  error: string | null;
  runAnalysis: (query: ProductQuery) => Promise<void>;
};

const emptyOptions: FilterOptions = { colors: [], conditions: [], materials: [], years: [] };

const OverviewContext = React.createContext<OverviewContextValue>({
  analysis: null,
  filterOptions: emptyOptions,
  shops: null,
  loading: true,
  analyzing: false,
  error: null,
  runAnalysis: async () => {},
});

export function useOverview() {
  return React.useContext(OverviewContext);
}

function buildSearchParams(query: ProductQuery, withOptions: boolean) {
  const params = new URLSearchParams();
  if (query.q.trim()) params.set("q", query.q.trim());
  for (const color of query.colors) {
    if (color) params.append("color", color);
  }
  for (const color of query.excludeColors) {
    if (color) params.append("excludeColor", color);
  }
  for (const condition of query.conditions) {
    if (condition) params.append("condition", condition);
  }
  for (const condition of query.excludeConditions) {
    if (condition) params.append("excludeCondition", condition);
  }
  for (const material of query.materials) {
    if (material) params.append("material", material);
  }
  for (const material of query.excludeMaterials) {
    if (material) params.append("excludeMaterial", material);
  }
  for (const year of query.years) {
    if (year) params.append("year", year);
  }
  for (const year of query.excludeYears) {
    if (year) params.append("excludeYear", year);
  }
  for (const shop of query.shops) {
    if (shop) params.append("shop", shop);
  }
  if (query.start) params.set("start", query.start);
  if (query.end) params.set("end", query.end);
  if (query.brand) params.set("brand", query.brand);
  if (query.product) params.set("product", query.product);
  if (withOptions) params.set("options", "1");
  return params;
}

export function OverviewProvider({ children }: { children: React.ReactNode }) {
  const [analysis, setAnalysis] = React.useState<ProductAnalysis | null>(null);
  const [filterOptions, setFilterOptions] = React.useState<FilterOptions>(emptyOptions);
  const [shops, setShops] = React.useState<ShopTotals | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [analyzing, setAnalyzing] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const runAnalysis = React.useCallback(async (query: ProductQuery) => {
    setAnalyzing(true);
    setError(null);
    try {
      const params = buildSearchParams(query, true);
      const res = await fetch(`/api/product-analysis?${params}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "分析失败");
      setAnalysis({
        keywords: json.keywords ?? [],
        filters: json.filters ?? {},
        products: json.products ?? [],
        matchedProductCount:
          json.matchedProductCount ?? (json.products?.length > 0 ? json.products.length : 0),
        summary: json.summary ?? { sampleCount: 0, avgPrice: null, minPrice: null, maxPrice: null },
        trend: json.trend ?? [],
        queryScopeSampleCount: json.queryScopeSampleCount ?? json.summary?.sampleCount ?? 0,
        conditionBreakdownTotal:
          json.conditionBreakdownTotal ?? json.queryScopeSampleCount ?? 0,
        colorBreakdownTotal: json.colorBreakdownTotal ?? json.queryScopeSampleCount ?? 0,
        breakdownByCondition: json.breakdownByCondition ?? [],
        breakdownByColor: json.breakdownByColor ?? [],
      });
      if (json.options) setFilterOptions(json.options);
    } catch (err) {
      setError(err instanceof Error ? err.message : "分析失败");
    } finally {
      setAnalyzing(false);
    }
  }, []);

  React.useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/dashboard");
        const json = await res.json();
        if (!res.ok) throw new Error(json.error ?? "加载失败");
        if (cancelled) return;
        setShops(json.shops ?? null);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "加载失败");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <OverviewContext.Provider
      value={{ analysis, filterOptions, shops, loading, analyzing, error, runAnalysis }}
    >
      {children}
    </OverviewContext.Provider>
  );
}
