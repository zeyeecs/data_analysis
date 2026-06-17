import type { AiTaskParams, AiTaskType } from "@/lib/ai-tasks/types";

type RemoteAgentConfig = {
  baseUrl: string;
  secret: string | null;
};

export function getRemoteAgentConfig(): RemoteAgentConfig | null {
  const baseUrl = process.env.SJKX_TASK_AGENT_URL?.trim();
  if (!baseUrl) return null;

  const secret = process.env.SJKX_TASK_AGENT_SECRET?.trim() || null;
  return { baseUrl: baseUrl.replace(/\/$/, ""), secret };
}

export function isRemoteAgentConfigured(): boolean {
  return getRemoteAgentConfig() !== null;
}

function buildHeaders(config: RemoteAgentConfig): HeadersInit {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (config.secret) {
    headers.Authorization = `Bearer ${config.secret}`;
  }
  return headers;
}

async function readResponseBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return { error: text.slice(0, 500) };
  }
}

export async function proxyRemoteAgentGet() {
  const config = getRemoteAgentConfig();
  if (!config) {
    throw new Error("未配置 SJKX_TASK_AGENT_URL");
  }

  const response = await fetch(`${config.baseUrl}/api/ai-tasks`, {
    method: "GET",
    headers: buildHeaders(config),
    cache: "no-store",
  });
  const payload = await readResponseBody(response);
  return { response, payload };
}

export async function proxyRemoteAgentPost(type: AiTaskType, params: AiTaskParams) {
  const config = getRemoteAgentConfig();
  if (!config) {
    throw new Error("未配置 SJKX_TASK_AGENT_URL");
  }

  const response = await fetch(`${config.baseUrl}/api/ai-tasks`, {
    method: "POST",
    headers: {
      ...buildHeaders(config),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ type, params }),
    cache: "no-store",
  });
  const payload = await readResponseBody(response);
  return { response, payload };
}

export async function proxyRemoteAgentDelete(taskId: string) {
  const config = getRemoteAgentConfig();
  if (!config) {
    throw new Error("未配置 SJKX_TASK_AGENT_URL");
  }

  const response = await fetch(
    `${config.baseUrl}/api/ai-tasks?id=${encodeURIComponent(taskId)}`,
    {
      method: "DELETE",
      headers: buildHeaders(config),
      cache: "no-store",
    },
  );
  const payload = await readResponseBody(response);
  return { response, payload };
}

export function getRemoteAgentAvailability(): { available: boolean; message: string | null } {
  if (!isRemoteAgentConfigured()) {
    return {
      available: false,
      message:
        "Vercel 无法本地执行 Python 任务。请在 Vercel 环境变量中配置 SJKX_TASK_AGENT_URL 指向 VPS 任务代理。",
    };
  }
  return {
    available: true,
    message: "任务将通过 VPS 任务代理远程执行。",
  };
}
