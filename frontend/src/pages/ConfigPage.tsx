import { Box } from "@chakra-ui/react";
import ApiKeyForm from "../components/config/ApiKeyForm";

export default function ConfigPage() {
  return (
    <Box className="max-w-2xl">
      <ApiKeyForm />
    </Box>
  );
}
