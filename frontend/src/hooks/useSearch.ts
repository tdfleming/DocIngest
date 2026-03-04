import { useMutation } from "@tanstack/react-query";
import { searchDocuments } from "../api/search";
import type { SearchRequest } from "../api/types";

export function useSearch() {
  return useMutation({
    mutationFn: (request: SearchRequest) => searchDocuments(request),
  });
}
