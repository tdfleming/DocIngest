import client from "./client";
import type { LogListParams, LogListResponse } from "./types";

export async function listLogs(
  params: LogListParams = {}
): Promise<LogListResponse> {
  const { data } = await client.get<LogListResponse>("/admin/logs", {
    params,
  });
  return data;
}
