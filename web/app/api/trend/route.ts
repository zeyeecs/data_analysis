import { NextRequest, NextResponse } from "next/server";

import { fetchModelPriceTrend } from "@/lib/db";
import { normalizeRange } from "@/lib/period";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const model = searchParams.get("model")?.trim() ?? "";
  const start = searchParams.get("start") ?? "";
  const end = searchParams.get("end") ?? "";

  if (!model) {
    return NextResponse.json({ error: "缺少型号关键字" }, { status: 400 });
  }
  if (!start || !end) {
    return NextResponse.json({ error: "缺少起止日期" }, { status: 400 });
  }

  const range = normalizeRange(start, end);

  try {
    const rows = await fetchModelPriceTrend(range.start, range.end, model);
    return NextResponse.json({ rows, range, model });
  } catch (err) {
    const message = err instanceof Error ? err.message : "查询失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
