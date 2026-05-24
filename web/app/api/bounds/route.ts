import { NextResponse } from "next/server";

import { fetchTableBounds } from "@/lib/db";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const bounds = await fetchTableBounds();
    return NextResponse.json({ bounds });
  } catch (err) {
    const message = err instanceof Error ? err.message : "查询失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
