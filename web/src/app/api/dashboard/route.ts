import { NextResponse } from "next/server";

import { fetchDashboardData } from "@/lib/sjkx-data";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await fetchDashboardData();
    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "查询失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
