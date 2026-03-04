import client from "./client";
import type {
  BatchUrlRequest,
  BatchUrlResponse,
  DeleteResponse,
  DocumentListParams,
  DocumentListResponse,
  DocumentResponse,
  ReprocessResponse,
  UploadResponse,
  UrlIngestRequest,
} from "./types";

export async function listDocuments(
  params: DocumentListParams = {}
): Promise<DocumentListResponse> {
  const { data } = await client.get<DocumentListResponse>("/documents", {
    params,
  });
  return data;
}

export async function getDocument(docId: string): Promise<DocumentResponse> {
  const { data } = await client.get<DocumentResponse>(`/documents/${docId}`);
  return data;
}

export async function uploadDocument(
  file: File,
  options?: { force?: boolean; chunk_size?: number; chunk_overlap?: number }
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const params: Record<string, string> = {};
  if (options?.force) params.force = "true";
  if (options?.chunk_size) params.chunk_size = String(options.chunk_size);
  if (options?.chunk_overlap)
    params.chunk_overlap = String(options.chunk_overlap);
  const { data } = await client.post<UploadResponse>("/documents", formData, {
    params,
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function ingestUrl(
  request: UrlIngestRequest
): Promise<UploadResponse> {
  const { data } = await client.post<UploadResponse>(
    "/documents/url",
    request
  );
  return data;
}

export async function ingestBatchUrls(
  request: BatchUrlRequest
): Promise<BatchUrlResponse> {
  const { data } = await client.post<BatchUrlResponse>(
    "/documents/batch",
    request
  );
  return data;
}

export async function deleteDocument(docId: string): Promise<DeleteResponse> {
  const { data } = await client.delete<DeleteResponse>(`/documents/${docId}`);
  return data;
}

export async function reprocessDocument(
  docId: string
): Promise<ReprocessResponse> {
  const { data } = await client.post<ReprocessResponse>(
    `/documents/${docId}/reprocess`
  );
  return data;
}

export async function getDocumentMarkdown(docId: string): Promise<string> {
  const { data } = await client.get<string>(`/documents/${docId}/markdown`);
  return data;
}
