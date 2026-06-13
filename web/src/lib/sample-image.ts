/** 从 image_urls / image 等文本字段提取首个 http(s) 图片地址 */
export function firstHttpImageUrl(...parts: (string | null | undefined)[]): string | null {
  for (const part of parts) {
    if (!part?.trim()) continue;
    const trimmed = part.trim();
    if (/^https?:\/\//i.test(trimmed)) return trimmed.split(/[\s,;]+/)[0] ?? trimmed;
    const match = trimmed.match(/https?:\/\/[^\s,;]+/i);
    if (match) return match[0];
  }
  return null;
}
