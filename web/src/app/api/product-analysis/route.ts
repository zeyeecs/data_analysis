import { NextRequest, NextResponse } from "next/server";

import {
  fetchFilterOptions,
  fetchProductAnalysis,
  parseProductAnalysisParams,
} from "@/lib/sjkx-product-analytics";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const params = parseProductAnalysisParams(request.nextUrl.searchParams);
    const includeOptions = request.nextUrl.searchParams.get("options") === "1";

    const analysis = await fetchProductAnalysis(params);
    const options = includeOptions
      ? await fetchFilterOptions({ keywords: params.keywords, shops: params.shops })
      : undefined;

    return NextResponse.json({ ...analysis, options });
  } catch (err) {
    const message = err instanceof Error ? err.message : "查询失败";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
