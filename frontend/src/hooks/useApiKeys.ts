import { useQuery } from "@tanstack/react-query";
import { listApiKeys } from "../api/apiKeys";

export function useApiKeys() {
  return useQuery({
    queryKey: ["apiKeys"],
    queryFn: listApiKeys,
  });
}
