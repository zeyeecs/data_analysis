import { NextRequest, NextResponse } from "next/server";

import {
  fetchProductSamples,
  parseProductSamplesParams,
} from "@/lib/sjkx-product-analytics";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const params = parseProductSamplesParams(request.nextUrl.searchParams);
    const result = await fetchProductSamples(params);
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "查询失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
