"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { TableBounds, TrendRow } from "@/lib/db";
import { buildPeriodSummary, defaultPeriodBounds, periodFromPreset } from "@/lib/period";

const PRESETS = [
  { label: "30 天", days: 30 },
  { label: "60 天", days: 60 },
  { label: "90 天", days: 90 },
] as const;

const COLUMN_ZH: Record<string, string> = {
  snapshot_date: "快照日期",
  currency: "货币",
  item_count: "样本件数",
  avg_price: "均价",
  min_price: "最低价",
  max_price: "最高价",
  median_price: "中位价",
  total_price: "成交总额",
};

function formatCell(key: string, value: unknown) {
  if (value == null) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return String(value);
}

export function PriceTrendApp() {
  const [bounds, setBounds] = useState<TableBounds | null>(null);
  const [boundsError, setBoundsError] = useState<string | null>(null);
  const [loadingBounds, setLoadingBounds] = useState(true);

  const [presetDays, setPresetDays] = useState<number | "custom">(30);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [model, setModel] = useState("");

  const [rows, setRows] = useState<TrendRow[]>([]);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [loadingTrend, setLoadingTrend] = useState(false);
  const [queried, setQueried] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingBounds(true);
      setBoundsError(null);
      try {
        const res = await fetch("/api/bounds");
        const data = await res.json();
        if (!res.ok) throw new Error(data.error ?? "无法连接数据库");
        if (cancelled) return;
        setBounds(data.bounds);
        const period = defaultPeriodBounds(data.bounds, 30);
        setStart(period.start);
        setEnd(period.end);
      } catch (err) {
        if (!cancelled) {
          setBoundsError(err instanceof Error ? err.message : "无法连接数据库");
        }
      } finally {
        if (!cancelled) setLoadingBounds(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const applyPreset = useCallback(
    (days: number) => {
      if (!bounds) return;
      const period = periodFromPreset(bounds, days);
      setPresetDays(days);
      setStart(period.start);
      setEnd(period.end);
    },
    [bounds],
  );

  const runQuery = useCallback(async () => {
    const keyword = model.trim();
    if (!keyword) return;

    setLoadingTrend(true);
    setQueryError(null);
    setQueried(true);

    try {
      const params = new URLSearchParams({ model: keyword, start, end });
      const res = await fetch(`/api/trend?${params}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "查询失败");
      setRows(data.rows ?? []);
    } catch (err) {
      setRows([]);
      setQueryError(err instanceof Error ? err.message : "查询失败");
    } finally {
      setLoadingTrend(false);
    }
  }, [model, start, end]);

  const summary = useMemo(() => buildPeriodSummary(rows), [rows]);

  const currencies = useMemo(
    () => [...new Set(rows.map((r) => r.currency))].sort(),
    [rows],
  );

  if (loadingBounds) {
    return <div className="info">正在连接数据库…</div>;
  }

  if (boundsError) {
    return (
      <div className="error">
        无法连接数据库，请检查 Vercel 环境变量 DATABASE_URL。
        <br />
        {boundsError}
      </div>
    );
  }

  return (
    <div className="layout">
      <aside className="panel">
        <h2>查询条件</h2>
        <div className="field">
          <label>时间区间</label>
          <div className="preset-row">
            {PRESETS.map((p) => (
              <button
                key={p.days}
                type="button"
                className={presetDays === p.days ? "active" : ""}
                onClick={() => applyPreset(p.days)}
              >
                {p.label}
              </button>
            ))}
            <button
              type="button"
              className={presetDays === "custom" ? "active" : ""}
              onClick={() => setPresetDays("custom")}
            >
              自定义
            </button>
          </div>
        </div>
        <div className="date-row">
          <div className="field">
            <label htmlFor="start">起始日</label>
            <input
              id="start"
              type="date"
              value={start}
              onChange={(e) => {
                setPresetDays("custom");
                setStart(e.target.value);
              }}
            />
          </div>
          <div className="field">
            <label htmlFor="end">结束日</label>
            <input
              id="end"
              type="date"
              value={end}
              onChange={(e) => {
                setPresetDays("custom");
                setEnd(e.target.value);
              }}
            />
          </div>
        </div>
        {start > end && (
          <p className="warn" style={{ marginTop: 0 }}>
            起始日晚于结束日，查询时将自动对调。
          </p>
        )}
        <div className="field">
          <label htmlFor="model">型号关键字</label>
          <input
            id="model"
            type="text"
            value={model}
            placeholder="必填，部分匹配"
            onChange={(e) => setModel(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void runQuery();
            }}
          />
        </div>
        <button
          type="button"
          className="primary"
          disabled={!model.trim() || loadingTrend}
          onClick={() => void runQuery()}
        >
          {loadingTrend ? "查询中…" : "查询"}
        </button>
      </aside>

      <section>
        {!model.trim() && !queried && (
          <div className="info">请在左侧输入型号关键字查看价格趋势。</div>
        )}

        {queryError && <div className="error">{queryError}</div>}

        {queried && !loadingTrend && !queryError && rows.length === 0 && model.trim() && (
          <div className="warn">
            在 {start} ~ {end} 内未找到匹配「{model.trim()}」的已售记录。
          </div>
        )}

        {rows.length > 0 && (
          <>
            <div className="info">
              型号「{model.trim()}」· {start} ~ {end}
            </div>

            {summary && (
              <>
                <h2 className="section-title">期间汇总</h2>
                <div className="metrics">
                  <div className="metric">
                    <div className="metric-label">样本件数</div>
                    <div className="metric-value">{summary.itemCount}</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">期间均价</div>
                    <div className="metric-value">{summary.avgPrice ?? "—"}</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">期间最低价</div>
                    <div className="metric-value">{summary.minPrice}</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">期间最高价</div>
                    <div className="metric-value">{summary.maxPrice}</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">快照日数</div>
                    <div className="metric-value">{summary.snapshotDays}</div>
                  </div>
                </div>
              </>
            )}

            {currencies.length > 1 && (
              <p className="caption">
                含 {currencies.length} 种货币（{currencies.join("，")}），分开展示，请勿直接比较数值。
              </p>
            )}

            {currencies.map((currency) => {
              const subset = rows
                .filter((r) => r.currency === currency)
                .sort((a, b) => a.snapshot_date.localeCompare(b.snapshot_date));
              const chartData = subset.map((r) => ({
                date: r.snapshot_date,
                均价: r.avg_price,
                中位价: r.median_price,
                最低价: r.min_price,
                最高价: r.max_price,
              }));
              const label = currency !== "—" ? `（${currency}）` : "";

              return (
                <div key={currency}>
                  <h2 className="section-title">价格趋势 {label}</h2>
                  {chartData.length > 0 ? (
                    <div className="chart-box">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line type="monotone" dataKey="均价" stroke="#1f4e79" dot={false} />
                          <Line type="monotone" dataKey="中位价" stroke="#2a9d8f" dot={false} />
                          <Line type="monotone" dataKey="最低价" stroke="#e76f51" dot={false} />
                          <Line type="monotone" dataKey="最高价" stroke="#f4a261" dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="caption">无价格数据。</p>
                  )}
                </div>
              );
            })}

            <h2 className="section-title">日度明细</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    {Object.keys(COLUMN_ZH).map((key) => (
                      <th key={key}>{COLUMN_ZH[key]}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, idx) => (
                    <tr key={`${row.snapshot_date}-${row.currency}-${idx}`}>
                      {Object.keys(COLUMN_ZH).map((key) => (
                        <td key={key}>{formatCell(key, row[key as keyof TrendRow])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
