import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardBody,
  HStack,
  Spinner,
  Table,
  Tbody,
  Text,
  Th,
  Thead,
  Tr,
  useDisclosure,
  useToast,
} from "@chakra-ui/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteDocument, reprocessDocument } from "../../api/documents";
import type { DocumentListParams, DocumentResponse } from "../../api/types";
import { useDocuments } from "../../hooks/useDocuments";
import FilterBar from "./FilterBar";
import DocumentRow from "./DocumentRow";
import DeleteConfirmDialog from "./DeleteConfirmDialog";
import MarkdownPreviewModal from "./MarkdownPreviewModal";

export default function DocumentTable() {
  const [status, setStatus] = useState("");
  const [contentType, setContentType] = useState("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const perPage = 20;

  const params: DocumentListParams = {
    page,
    per_page: perPage,
    sort: "created_at",
    order: sortOrder,
    ...(status && { status }),
    ...(contentType && { content_type: contentType }),
  };

  const { data, isLoading } = useDocuments(params);
  const toast = useToast();
  const qc = useQueryClient();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [deleteTarget, setDeleteTarget] = useState<DocumentResponse | null>(
    null
  );
  const [reprocessingId, setReprocessingId] = useState<string | null>(null);
  const [previewDocId, setPreviewDocId] = useState<string | null>(null);
  const {
    isOpen: isPreviewOpen,
    onOpen: onPreviewOpen,
    onClose: onPreviewClose,
  } = useDisclosure();

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => deleteDocument(docId),
    onSuccess: () => {
      toast({ title: "Document deleted", status: "success", duration: 2000 });
      qc.invalidateQueries({ queryKey: ["documents"] });
      onClose();
    },
    onError: () => {
      toast({ title: "Delete failed", status: "error", duration: 3000 });
    },
  });

  const reprocessMutation = useMutation({
    mutationFn: (docId: string) => reprocessDocument(docId),
    onSuccess: (data) => {
      toast({
        title: `Reprocessing started (v${data.version})`,
        status: "info",
        duration: 2000,
      });
      qc.invalidateQueries({ queryKey: ["documents"] });
      setReprocessingId(null);
    },
    onError: () => {
      toast({ title: "Reprocess failed", status: "error", duration: 3000 });
      setReprocessingId(null);
    },
  });

  const handleDelete = (doc: DocumentResponse) => {
    setDeleteTarget(doc);
    onOpen();
  };

  const confirmDelete = () => {
    if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
  };

  const handleReprocess = (docId: string) => {
    setReprocessingId(docId);
    reprocessMutation.mutate(docId);
  };

  const handleViewMarkdown = (docId: string) => {
    setPreviewDocId(docId);
    onPreviewOpen();
  };

  const totalPages = data ? Math.ceil(data.total / perPage) : 0;

  return (
    <Box>
      <FilterBar
        status={status}
        contentType={contentType}
        sortOrder={sortOrder}
        onStatusChange={(v) => { setStatus(v); setPage(1); }}
        onContentTypeChange={(v) => { setContentType(v); setPage(1); }}
        onSortOrderChange={(v) => { setSortOrder(v as "asc" | "desc"); setPage(1); }}
      />

      <Card className="mt-4" size="sm">
        <CardBody className="p-0">
          {isLoading ? (
            <Box className="p-8 text-center">
              <Spinner />
            </Box>
          ) : !data?.documents.length ? (
            <Text className="p-4 text-gray-500">No documents found</Text>
          ) : (
            <Table size="sm">
              <Thead>
                <Tr>
                  <Th>Source</Th>
                  <Th>Type</Th>
                  <Th>Status</Th>
                  <Th>Size</Th>
                  <Th>Chunks</Th>
                  <Th>Version</Th>
                  <Th>Created</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {data.documents.map((doc) => (
                  <DocumentRow
                    key={doc.id}
                    doc={doc}
                    onDelete={handleDelete}
                    onReprocess={handleReprocess}
                    onViewMarkdown={handleViewMarkdown}
                    isReprocessing={reprocessingId === doc.id}
                  />
                ))}
              </Tbody>
            </Table>
          )}
        </CardBody>
      </Card>

      {totalPages > 1 && (
        <HStack className="mt-4" justify="center" spacing={2}>
          <Button
            size="sm"
            isDisabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <Text className="text-sm text-gray-600">
            Page {page} of {totalPages}
          </Text>
          <Button
            size="sm"
            isDisabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </HStack>
      )}

      <DeleteConfirmDialog
        isOpen={isOpen}
        onClose={onClose}
        onConfirm={confirmDelete}
        isLoading={deleteMutation.isPending}
        sourceRef={deleteTarget?.source_ref ?? ""}
      />

      <MarkdownPreviewModal
        docId={previewDocId}
        isOpen={isPreviewOpen}
        onClose={onPreviewClose}
      />
    </Box>
  );
}
