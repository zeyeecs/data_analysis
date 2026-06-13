/** 规范化 Neon 连接串，避免 Prisma 不兼容参数与冷启动瞬时失败 */
export function normalizeDatabaseUrl(url: string): string {
  let value = url.trim();
  if (
    (value.startsWith("'") && value.endsWith("'")) ||
    (value.startsWith('"') && value.endsWith('"'))
  ) {
    value = value.slice(1, -1);
  }

  const parsed = new URL(value);
  parsed.searchParams.delete("channel_binding");
  if (!parsed.searchParams.has("sslmode")) {
    parsed.searchParams.set("sslmode", "require");
  }
  if (!parsed.searchParams.has("connect_timeout")) {
    parsed.searchParams.set("connect_timeout", "15");
  }

  return parsed.toString();
}

export function isTransientDbError(message: string) {
  return (
    message.includes("Can't reach database server") ||
    message.includes("Connection timed out") ||
    message.includes("ECONNREFUSED") ||
    message.includes("ENOTFOUND") ||
    message.includes("connection closed")
  );
}
