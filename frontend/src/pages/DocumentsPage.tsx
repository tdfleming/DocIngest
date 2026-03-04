import { Alert, AlertIcon, VStack } from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { useApiKey } from "../contexts/ApiKeyContext";
import UploadForm from "../components/documents/UploadForm";
import DocumentTable from "../components/documents/DocumentTable";

export default function DocumentsPage() {
  const { isSet } = useApiKey();

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
      <UploadForm />
      <DocumentTable />
    </VStack>
  );
}
