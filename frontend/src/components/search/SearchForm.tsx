import { useState } from "react";
import {
  Box,
  Button,
  Card,
  CardBody,
  Checkbox,
  FormControl,
  FormLabel,
  HStack,
  Input,
  Select,
  VStack,
} from "@chakra-ui/react";
import type { SearchRequest } from "../../api/types";

interface SearchFormProps {
  onSearch: (request: SearchRequest) => void;
  isLoading: boolean;
}

export default function SearchForm({ onSearch, isLoading }: SearchFormProps) {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(10);
  const [contentType, setContentType] = useState("");
  const [rerank, setRerank] = useState(true);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    const request: SearchRequest = {
      query: query.trim(),
      limit,
      rerank,
    };
    if (contentType) {
      request.filters = { content_type: [contentType] };
    }
    onSearch(request);
  };

  return (
    <Card size="sm">
      <CardBody>
        <form onSubmit={handleSubmit}>
          <VStack spacing={4} align="stretch">
            <FormControl>
              <FormLabel className="text-sm">Search Query</FormLabel>
              <Input
                placeholder="Enter your search query..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </FormControl>
            <HStack spacing={4}>
              <FormControl w="120px">
                <FormLabel className="text-xs">Limit</FormLabel>
                <Select
                  size="sm"
                  value={limit}
                  onChange={(e) => setLimit(Number(e.target.value))}
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </Select>
              </FormControl>
              <FormControl w="140px">
                <FormLabel className="text-xs">Content Type</FormLabel>
                <Select
                  size="sm"
                  value={contentType}
                  onChange={(e) => setContentType(e.target.value)}
                >
                  <option value="">All</option>
                  <option value="pdf">PDF</option>
                  <option value="html">HTML</option>
                  <option value="docx">DOCX</option>
                  <option value="txt">TXT</option>
                  <option value="md">Markdown</option>
                </Select>
              </FormControl>
              <Box className="pt-5">
                <Checkbox
                  isChecked={rerank}
                  onChange={(e) => setRerank(e.target.checked)}
                  size="sm"
                >
                  Rerank
                </Checkbox>
              </Box>
            </HStack>
            <Button
              type="submit"
              colorScheme="blue"
              isLoading={isLoading}
              isDisabled={!query.trim()}
            >
              Search
            </Button>
          </VStack>
        </form>
      </CardBody>
    </Card>
  );
}
