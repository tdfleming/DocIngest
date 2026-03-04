import { Badge, Box, Card, CardBody, HStack, Text } from "@chakra-ui/react";
import type { SearchResult } from "../../api/types";

interface SearchResultCardProps {
  result: SearchResult;
  rank: number;
}

export default function SearchResultCard({
  result,
  rank,
}: SearchResultCardProps) {
  return (
    <Card size="sm">
      <CardBody>
        <HStack justify="space-between" className="mb-2">
          <HStack spacing={2}>
            <Badge colorScheme="blue" variant="subtle">
              #{rank}
            </Badge>
            <Text className="text-sm font-medium" color="gray.700">
              {result.source_ref}
            </Text>
            <Badge variant="outline">{result.content_type}</Badge>
          </HStack>
          <Badge colorScheme="green" variant="subtle">
            {(result.score * 100).toFixed(1)}%
          </Badge>
        </HStack>

        {result.heading_chain.length > 0 && (
          <Text className="text-xs text-gray-400 mb-2">
            {result.heading_chain.join(" > ")}
          </Text>
        )}

        <Box
          className="text-sm whitespace-pre-wrap rounded p-3"
          bg="gray.50"
          borderWidth="1px"
          borderColor="gray.200"
        >
          {result.chunk_text}
        </Box>

        <Text className="mt-2 text-xs text-gray-400">
          Chunk #{result.chunk_index} &middot; Doc {result.doc_id}
        </Text>
      </CardBody>
    </Card>
  );
}
