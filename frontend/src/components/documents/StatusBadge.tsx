import { Badge } from "@chakra-ui/react";
import type { DocumentStatus } from "../../api/types";

const STATUS_COLORS: Record<DocumentStatus, string> = {
  pending: "yellow",
  converting: "blue",
  converted: "cyan",
  chunking: "purple",
  complete: "green",
  failed: "red",
};

interface StatusBadgeProps {
  status: DocumentStatus;
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <Badge colorScheme={STATUS_COLORS[status] ?? "gray"} variant="subtle">
      {status}
    </Badge>
  );
}
