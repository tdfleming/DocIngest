import { useState } from "react";
import {
  Badge,
  Box,
  Button,
  Code,
  Flex,
  HStack,
  Input,
  Select,
  Spinner,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
} from "@chakra-ui/react";
import type { LogEntry, LogListParams } from "../../api/types";
import { useLogs } from "../../hooks/useLogs";

const levelColors: Record<string, string> = {
  info: "blue",
  warning: "orange",
  error: "red",
};

export default function LogTable() {
  const [level, setLevel] = useState("");
  const [component, setComponent] = useState("");
  const [traceId, setTraceId] = useState("");
  const [docId, setDocId] = useState("");
  const [page, setPage] = useState(1);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const perPage = 50;

  const params: LogListParams = {
    page,
    per_page: perPage,
    ...(level && { level }),
    ...(component && { component }),
    ...(traceId && { trace_id: traceId }),
    ...(docId && { doc_id: docId }),
  };

  const { data, isLoading } = useLogs(params, autoRefresh);
  const totalPages = data ? Math.ceil(data.total / perPage) : 0;

  return (
    <Box>
      {/* Filter bar */}
      <Flex className="gap-3 mb-4 flex-wrap items-center">
        <Select
          size="sm"
          className="w-32"
          placeholder="All Levels"
          value={level}
          onChange={(e) => {
            setLevel(e.target.value);
            setPage(1);
          }}
        >
          <option value="info">Info</option>
          <option value="warning">Warning</option>
          <option value="error">Error</option>
        </Select>
        <Select
          size="sm"
          className="w-40"
          placeholder="All Components"
          value={component}
          onChange={(e) => {
            setComponent(e.target.value);
            setPage(1);
          }}
        >
          <option value="middleware">Middleware</option>
          <option value="auth">Auth</option>
          <option value="converter">Converter</option>
          <option value="chunker">Chunker</option>
        </Select>
        <Input
          size="sm"
          className="w-40"
          placeholder="Trace ID"
          value={traceId}
          onChange={(e) => {
            setTraceId(e.target.value);
            setPage(1);
          }}
        />
        <Input
          size="sm"
          className="w-40"
          placeholder="Doc ID"
          value={docId}
          onChange={(e) => {
            setDocId(e.target.value);
            setPage(1);
          }}
        />
        <HStack>
          <Text className="text-xs text-gray-500">Auto-refresh</Text>
          <Switch
            size="sm"
            isChecked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
        </HStack>
      </Flex>

      {isLoading ? (
        <Box className="p-8 text-center">
          <Spinner />
        </Box>
      ) : !data?.logs.length ? (
        <Text className="p-4 text-gray-500">No logs found</Text>
      ) : (
        <>
          <Table size="sm">
            <Thead>
              <Tr>
                <Th>Time</Th>
                <Th>Level</Th>
                <Th>Component</Th>
                <Th>Event</Th>
                <Th>Trace ID</Th>
              </Tr>
            </Thead>
            <Tbody>
              {data.logs.map((log: LogEntry) => (
                <>
                  <Tr
                    key={log.id}
                    className="cursor-pointer"
                    _hover={{ bg: "gray.50" }}
                    onClick={() =>
                      setExpandedId(expandedId === log.id ? null : log.id)
                    }
                  >
                    <Td className="text-xs text-gray-500 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </Td>
                    <Td>
                      <Badge
                        colorScheme={levelColors[log.level] ?? "gray"}
                        variant="subtle"
                        size="sm"
                      >
                        {log.level}
                      </Badge>
                    </Td>
                    <Td className="text-xs">{log.component}</Td>
                    <Td className="text-xs font-medium">{log.event}</Td>
                    <Td className="text-xs text-gray-400 font-mono">
                      {log.trace_id ?? "—"}
                    </Td>
                  </Tr>
                  {expandedId === log.id && (
                    <Tr key={`${log.id}-details`}>
                      <Td colSpan={5} className="bg-gray-50">
                        <Box className="p-2 text-xs space-y-1">
                          {log.doc_id && (
                            <Text>
                              <strong>Doc ID:</strong> {log.doc_id}
                            </Text>
                          )}
                          {log.tenant_id && (
                            <Text>
                              <strong>Tenant:</strong> {log.tenant_id}
                            </Text>
                          )}
                          {log.user_id && (
                            <Text>
                              <strong>User:</strong> {log.user_id}
                            </Text>
                          )}
                          {log.details && (
                            <Box>
                              <Text className="font-semibold mb-1">
                                Details:
                              </Text>
                              <Code className="block p-2 text-xs whitespace-pre-wrap">
                                {JSON.stringify(log.details, null, 2)}
                              </Code>
                            </Box>
                          )}
                          {log.error && (
                            <Box>
                              <Text className="font-semibold text-red-600 mb-1">
                                Error:
                              </Text>
                              <Code
                                colorScheme="red"
                                className="block p-2 text-xs whitespace-pre-wrap"
                              >
                                {log.error}
                              </Code>
                            </Box>
                          )}
                        </Box>
                      </Td>
                    </Tr>
                  )}
                </>
              ))}
            </Tbody>
          </Table>

          {totalPages > 1 && (
            <HStack className="mt-4" justify="center" spacing={2}>
              <Button
                size="sm"
                isDisabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Text className="text-sm text-gray-600">
                Page {page} of {totalPages}
              </Text>
              <Button
                size="sm"
                isDisabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </HStack>
          )}
        </>
      )}
    </Box>
  );
}
