import { Alert, AlertIcon, VStack } from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { useApiKey } from "../contexts/ApiKeyContext";
import { useSearch } from "../hooks/useSearch";
import SearchForm from "../components/search/SearchForm";
import SearchResults from "../components/search/SearchResults";

export default function SearchPage() {
  const { isSet } = useApiKey();
  const search = useSearch();

  if (!isSet) {
    return (
      <Alert status="warning" borderRadius="md">
        <AlertIcon />
        API key required.{" "}
        <Link to="/config" className="ml-1 underline font-medium">
          Set one in Configuration
        </Link>
      </Alert>
    );
  }

  return (
    <VStack spacing={6} align="stretch">
      <SearchForm onSearch={search.mutate} isLoading={search.isPending} />
      {search.data && <SearchResults data={search.data} />}
      {search.isError && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          Search failed. Please check your query and try again.
        </Alert>
      )}
    </VStack>
  );
}
