import { Card, CardBody } from "@chakra-ui/react";
import LogTable from "../components/logs/LogTable";

export default function LogsPage() {
  return (
    <Card size="sm">
      <CardBody>
        <LogTable />
      </CardBody>
    </Card>
  );
}
