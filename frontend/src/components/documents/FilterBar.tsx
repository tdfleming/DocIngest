import { HStack, Select } from "@chakra-ui/react";

interface FilterBarProps {
  status: string;
  contentType: string;
  sortOrder: string;
  onStatusChange: (v: string) => void;
  onContentTypeChange: (v: string) => void;
  onSortOrderChange: (v: string) => void;
}

export default function FilterBar({
  status,
  contentType,
  sortOrder,
  onStatusChange,
  onContentTypeChange,
  onSortOrderChange,
}: FilterBarProps) {
  return (
    <HStack spacing={3}>
      <Select
        size="sm"
        w="160px"
        value={status}
        onChange={(e) => onStatusChange(e.target.value)}
      >
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="converting">Converting</option>
        <option value="converted">Converted</option>
        <option value="chunking">Chunking</option>
        <option value="complete">Complete</option>
        <option value="failed">Failed</option>
      </Select>
      <Select
        size="sm"
        w="140px"
        value={contentType}
        onChange={(e) => onContentTypeChange(e.target.value)}
      >
        <option value="">All Types</option>
        <option value="pdf">PDF</option>
        <option value="html">HTML</option>
        <option value="docx">DOCX</option>
        <option value="txt">TXT</option>
        <option value="md">Markdown</option>
      </Select>
      <Select
        size="sm"
        w="160px"
        value={sortOrder}
        onChange={(e) => onSortOrderChange(e.target.value)}
      >
        <option value="desc">Newest First</option>
        <option value="asc">Oldest First</option>
      </Select>
    </HStack>
  );
}
