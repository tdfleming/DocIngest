import client from "./client";
import type { SearchRequest, SearchResponse } from "./types";

export async function searchDocuments(
  request: SearchRequest
): Promise<SearchResponse> {
  const { data } = await client.post<SearchResponse>("/search", request);
  return data;
}
