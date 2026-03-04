import { useCallback, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  FormControl,
  FormLabel,
  Heading,
  Input,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Text,
  Textarea,
  useToast,
  VStack,
} from "@chakra-ui/react";
import { useDropzone } from "react-dropzone";
import { FiUpload } from "react-icons/fi";
import { useUploadFile, useIngestUrl, useIngestBatchUrls } from "../../hooks/useUpload";

export default function UploadForm() {
  const toast = useToast();
  const uploadFile = useUploadFile();
  const ingestUrl = useIngestUrl();
  const ingestBatch = useIngestBatchUrls();

  const [url, setUrl] = useState("");
  const [batchUrls, setBatchUrls] = useState("");

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      for (const file of acceptedFiles) {
        uploadFile.mutate(file, {
          onSuccess: (data) => {
            const msg = data.existing
              ? `${file.name}: duplicate detected`
              : `${file.name}: upload started`;
            toast({
              title: msg,
              status: data.existing ? "warning" : "success",
              duration: 3000,
            });
          },
          onError: () => {
            toast({
              title: `Failed to upload ${file.name}`,
              status: "error",
              duration: 4000,
            });
          },
        });
      }
    },
    [uploadFile, toast]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/html": [".html", ".htm"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
      "text/plain": [".txt"],
      "text/markdown": [".md", ".markdown"],
    },
  });

  const handleUrlSubmit = () => {
    if (!url.trim()) return;
    ingestUrl.mutate(
      { url: url.trim() },
      {
        onSuccess: () => {
          toast({ title: "URL ingestion started", status: "success", duration: 2000 });
          setUrl("");
        },
        onError: () => {
          toast({ title: "URL ingestion failed", status: "error", duration: 3000 });
        },
      }
    );
  };

  const handleBatchSubmit = () => {
    const urls = batchUrls
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (!urls.length) return;
    ingestBatch.mutate(
      { urls },
      {
        onSuccess: (data) => {
          const ok = data.results.filter((r) => r.status === "pending").length;
          const fail = data.results.filter((r) => r.status === "error").length;
          toast({
            title: `Batch: ${ok} started, ${fail} failed`,
            status: fail > 0 ? "warning" : "success",
            duration: 3000,
          });
          setBatchUrls("");
        },
        onError: () => {
          toast({ title: "Batch ingestion failed", status: "error", duration: 3000 });
        },
      }
    );
  };

  return (
    <Card size="sm">
      <CardHeader>
        <Heading size="sm">Ingest Documents</Heading>
      </CardHeader>
      <CardBody>
        <Tabs size="sm" variant="enclosed">
          <TabList>
            <Tab>File Upload</Tab>
            <Tab>URL</Tab>
            <Tab>Batch URLs</Tab>
          </TabList>
          <TabPanels>
            <TabPanel>
              <Box
                {...getRootProps()}
                className="border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors"
                borderColor={isDragActive ? "brand.400" : "gray.300"}
                bg={isDragActive ? "brand.50" : "gray.50"}
                _hover={{ borderColor: "brand.300" }}
              >
                <input {...getInputProps()} />
                <VStack spacing={2}>
                  <Box color="gray.400">
                    <FiUpload size={32} />
                  </Box>
                  <Text className="text-sm text-gray-600">
                    {isDragActive
                      ? "Drop files here..."
                      : "Drag & drop files, or click to select"}
                  </Text>
                  <Text className="text-xs text-gray-400">
                    PDF, HTML, DOCX, TXT, Markdown
                  </Text>
                </VStack>
              </Box>
              {uploadFile.isPending && (
                <Text className="mt-2 text-sm text-gray-500">Uploading...</Text>
              )}
            </TabPanel>
            <TabPanel>
              <VStack spacing={3} align="stretch">
                <FormControl>
                  <FormLabel className="text-sm">Document URL</FormLabel>
                  <Input
                    size="sm"
                    placeholder="https://example.com/document.pdf"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                  />
                </FormControl>
                <Button
                  size="sm"
                  colorScheme="blue"
                  onClick={handleUrlSubmit}
                  isLoading={ingestUrl.isPending}
                  isDisabled={!url.trim()}
                >
                  Ingest URL
                </Button>
              </VStack>
            </TabPanel>
            <TabPanel>
              <VStack spacing={3} align="stretch">
                <FormControl>
                  <FormLabel className="text-sm">URLs (one per line)</FormLabel>
                  <Textarea
                    size="sm"
                    rows={5}
                    placeholder={"https://example.com/doc1.pdf\nhttps://example.com/doc2.html"}
                    value={batchUrls}
                    onChange={(e) => setBatchUrls(e.target.value)}
                  />
                </FormControl>
                <Button
                  size="sm"
                  colorScheme="blue"
                  onClick={handleBatchSubmit}
                  isLoading={ingestBatch.isPending}
                  isDisabled={!batchUrls.trim()}
                >
                  Ingest Batch
                </Button>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </CardBody>
    </Card>
  );
}
