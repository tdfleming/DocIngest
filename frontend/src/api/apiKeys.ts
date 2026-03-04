import client from "./client";
import type {
  ApiKeyEntry,
  CreateApiKeyRequest,
  CreateApiKeyResponse,
  UpdateApiKeyRequest,
} from "./types";

export async function listApiKeys(): Promise<ApiKeyEntry[]> {
  const { data } = await client.get<ApiKeyEntry[]>("/admin/api-keys");
  return data;
}

export async function createApiKey(
  request: CreateApiKeyRequest
): Promise<CreateApiKeyResponse> {
  const { data } = await client.post<CreateApiKeyResponse>(
    "/admin/api-keys",
    request
  );
  return data;
}

export async function updateApiKey(
  keyId: string,
  request: UpdateApiKeyRequest
): Promise<ApiKeyEntry> {
  const { data } = await client.patch<ApiKeyEntry>(
    `/admin/api-keys/${keyId}`,
    request
  );
  return data;
}

export async function deleteApiKey(
  keyId: string
): Promise<{ id: string; status: string }> {
  const { data } = await client.delete(`/admin/api-keys/${keyId}`);
  return data;
}
