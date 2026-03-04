import client from "./client";
import type { HealthCheck } from "./types";

export async function getHealth(): Promise<HealthCheck> {
  const { data } = await client.get<HealthCheck>("/health");
  return data;
}
