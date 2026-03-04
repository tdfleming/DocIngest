import { useQuery } from "@tanstack/react-query";
import { getDocument, listDocuments } from "../api/documents";
import type { DocumentListParams, DocumentStatus } from "../api/types";

const PROCESSING_STATUSES: DocumentStatus[] = [
  "pending",
  "converting",
  "converted",
  "chunking",
];

export function useDocuments(params: DocumentListParams = {}) {
  return useQuery({
    queryKey: ["documents", params],
    queryFn: () => listDocuments(params),
    refetchInterval: (query) => {
      const docs = query.state.data?.documents;
      if (docs?.some((d) => PROCESSING_STATUSES.includes(d.status))) {
        return 5_000;
      }
      return false;
    },
  });
}

export function useDocument(docId: string | undefined) {
  return useQuery({
    queryKey: ["document", docId],
    queryFn: () => getDocument(docId!),
    enabled: !!docId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status && PROCESSING_STATUSES.includes(status)) {
        return 5_000;
      }
      return false;
    },
  });
}
