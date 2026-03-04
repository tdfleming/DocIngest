import { Box, HStack, Text, VStack } from "@chakra-ui/react";
import type { SearchResponse } from "../../api/types";
import SearchResultCard from "./SearchResultCard";

interface SearchResultsProps {
  data: SearchResponse;
}

export default function SearchResults({ data }: SearchResultsProps) {
  if (data.results.length === 0) {
    return (
      <Text className="text-gray-500 text-center py-8">
        No results found
      </Text>
    );
  }

  return (
    <VStack spacing={3} align="stretch">
      <HStack className="text-xs text-gray-500" spacing={4}>
        <Text>{data.results.length} results</Text>
        <Text>{data.search_time_ms}ms</Text>
        <Text>~{data.query_tokens} query tokens</Text>
      </HStack>
      <Box>
        <VStack spacing={3} align="stretch">
          {data.results.map((result, i) => (
            <SearchResultCard key={i} result={result} rank={i + 1} />
          ))}
        </VStack>
      </Box>
    </VStack>
  );
}
