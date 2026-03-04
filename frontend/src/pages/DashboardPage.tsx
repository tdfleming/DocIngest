import { Alert, AlertIcon, VStack } from "@chakra-ui/react";
import { Link } from "react-router-dom";
import { useApiKey } from "../contexts/ApiKeyContext";
import HealthPanel from "../components/dashboard/HealthPanel";
import StatsPanel from "../components/dashboard/StatsPanel";
import RecentDocuments from "../components/dashboard/RecentDocuments";

export default function DashboardPage() {
  const { isSet } = useApiKey();

  return (
    <VStack spacing={6} align="stretch">
      {!isSet && (
        <Alert status="warning" borderRadius="md">
          <AlertIcon />
          No API key configured.{" "}
          <Link to="/config" className="ml-1 underline font-medium">
            Set one in Configuration
          </Link>
        </Alert>
      )}
      <HealthPanel />
      {isSet && (
        <>
          <StatsPanel />
          <RecentDocuments />
        </>
      )}
    </VStack>
  );
}
