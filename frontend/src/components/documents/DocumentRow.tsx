import { IconButton, Td, Tooltip, Tr } from "@chakra-ui/react";
import { FiEye, FiRefreshCw, FiTrash2 } from "react-icons/fi";
import type { DocumentResponse } from "../../api/types";
import StatusBadge from "./StatusBadge";

interface DocumentRowProps {
  doc: DocumentResponse;
  onDelete: (doc: DocumentResponse) => void;
  onReprocess: (docId: string) => void;
  onViewMarkdown?: (docId: string) => void;
  isReprocessing: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export default function DocumentRow({
  doc,
  onDelete,
  onReprocess,
  onViewMarkdown,
  isReprocessing,
}: DocumentRowProps) {
  const canViewMarkdown =
    doc.status === "converted" || doc.status === "chunking" || doc.status === "complete";

  return (
    <Tr>
      <Td className="max-w-xs truncate" title={doc.source_ref}>
        {doc.source_ref}
      </Td>
      <Td>{doc.content_type}</Td>
      <Td>
        <StatusBadge status={doc.status} />
      </Td>
      <Td className="text-xs">{formatBytes(doc.file_size_bytes)}</Td>
      <Td>{doc.chunk_count}</Td>
      <Td>v{doc.version}</Td>
      <Td className="text-xs text-gray-500">
        {new Date(doc.created_at).toLocaleString()}
      </Td>
      <Td>
        {canViewMarkdown && onViewMarkdown && (
          <Tooltip label="View Markdown">
            <IconButton
              aria-label="View Markdown"
              icon={<FiEye />}
              size="xs"
              variant="ghost"
              colorScheme="blue"
              onClick={() => onViewMarkdown(doc.id)}
            />
          </Tooltip>
        )}
        <Tooltip label="Reprocess">
          <IconButton
            aria-label="Reprocess"
            icon={<FiRefreshCw />}
            size="xs"
            variant="ghost"
            onClick={() => onReprocess(doc.id)}
            isLoading={isReprocessing}
            isDisabled={doc.status === "pending" || doc.status === "converting" || doc.status === "chunking"}
          />
        </Tooltip>
        <Tooltip label="Delete">
          <IconButton
            aria-label="Delete"
            icon={<FiTrash2 />}
            size="xs"
            variant="ghost"
            colorScheme="red"
            onClick={() => onDelete(doc)}
            className="ml-1"
          />
        </Tooltip>
      </Td>
    </Tr>
  );
}
