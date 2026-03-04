import {
  Box,
  Flex,
  IconButton,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalHeader,
  ModalOverlay,
  Spinner,
  Tooltip,
  useToast,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { FiCopy } from "react-icons/fi";
import ReactMarkdown from "react-markdown";
import { getDocumentMarkdown } from "../../api/documents";

interface MarkdownPreviewModalProps {
  docId: string | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function MarkdownPreviewModal({
  docId,
  isOpen,
  onClose,
}: MarkdownPreviewModalProps) {
  const toast = useToast();

  const { data: markdown, isLoading } = useQuery({
    queryKey: ["documentMarkdown", docId],
    queryFn: () => getDocumentMarkdown(docId!),
    enabled: isOpen && !!docId,
  });

  const copyRaw = () => {
    if (markdown) {
      navigator.clipboard.writeText(markdown);
      toast({ title: "Copied to clipboard", status: "info", duration: 1500 });
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="4xl">
      <ModalOverlay />
      <ModalContent maxH="80vh">
        <ModalHeader>
          <Flex className="items-center justify-between pr-8">
            Markdown Preview
            <Tooltip label="Copy raw markdown">
              <IconButton
                aria-label="Copy raw"
                icon={<FiCopy />}
                size="sm"
                variant="ghost"
                onClick={copyRaw}
                isDisabled={!markdown}
              />
            </Tooltip>
          </Flex>
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody className="overflow-y-auto pb-6">
          {isLoading ? (
            <Flex className="justify-center p-8">
              <Spinner />
            </Flex>
          ) : markdown ? (
            <Box className="prose prose-sm max-w-none">
              <ReactMarkdown>{markdown}</ReactMarkdown>
            </Box>
          ) : (
            <Box className="text-gray-500">No markdown available</Box>
          )}
        </ModalBody>
      </ModalContent>
    </Modal>
  );
}
