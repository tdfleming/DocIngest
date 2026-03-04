import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ingestBatchUrls,
  ingestUrl,
  uploadDocument,
} from "../api/documents";
import type { BatchUrlRequest, UrlIngestRequest } from "../api/types";

export function useUploadFile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => uploadDocument(file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useIngestUrl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (request: UrlIngestRequest) => ingestUrl(request),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useIngestBatchUrls() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (request: BatchUrlRequest) => ingestBatchUrls(request),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}
