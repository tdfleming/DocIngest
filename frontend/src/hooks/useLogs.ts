import { useQuery } from "@tanstack/react-query";
import { listLogs } from "../api/logs";
import type { LogListParams } from "../api/types";

export function useLogs(params: LogListParams = {}, autoRefresh = false) {
  return useQuery({
    queryKey: ["logs", params],
    queryFn: () => listLogs(params),
    refetchInterval: autoRefresh ? 5000 : false,
  });
}
