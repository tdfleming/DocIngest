// Health
export interface HealthCheck {
  status: "healthy" | "degraded";
  checks: {
    mongodb: "ok" | "error";
    qdrant: "ok" | "error";
    redis: "ok" | "error";
    minio: "ok" | "error";
  };
}

// Documents
export type DocumentStatus =
  | "pending"
  | "converting"
  | "converted"
  | "chunking"
  | "complete"
  | "failed";

export type ContentType = "pdf" | "html" | "docx" | "txt" | "md";
export type SourceType = "url" | "upload" | "batch" | "watch";

export interface DocumentResponse {
  id: string;
  tenant_id: string;
  source_type: SourceType;
  source_ref: string;
  content_type: ContentType;
  status: DocumentStatus;
  error: string | null;
  error_type: string | null;
  error_stage: string | null;
  file_size_bytes: number;
  chunk_count: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: DocumentResponse[];
  total: number;
  page: number;
  per_page: number;
}

export interface DocumentListParams {
  status?: string;
  content_type?: string;
  page?: number;
  per_page?: number;
  sort?: string;
  order?: "asc" | "desc";
}

export interface UploadResponse {
  id: string;
  status: string;
  existing?: boolean;
}

export interface UrlIngestRequest {
  url: string;
  force?: boolean;
  chunk_size?: number;
  chunk_overlap?: number;
  chunking_strategy?: string;
}

export interface BatchUrlRequest {
  urls: string[];
  force?: boolean;
}

export interface BatchUrlResult {
  url: string;
  id?: string;
  status: string;
  error?: string;
}

export interface BatchUrlResponse {
  results: BatchUrlResult[];
}

export interface DeleteResponse {
  id: string;
  status: "deleted";
}

export interface ReprocessResponse {
  id: string;
  status: string;
  version: number;
}

// Search
export interface SearchFilters {
  content_type?: string[];
  source_ref?: string;
}

export interface SearchRequest {
  query: string;
  limit?: number;
  filters?: SearchFilters;
  rerank?: boolean;
}

export interface SearchResult {
  chunk_text: string;
  score: number;
  doc_id: string;
  source_ref: string;
  content_type: string;
  heading_chain: string[];
  chunk_index: number;
}

export interface SearchResponse {
  results: SearchResult[];
  query_tokens: number;
  search_time_ms: number;
}

// Auth
export type UserRole = "admin" | "viewer";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserResponse;
}

export interface UserResponse {
  id: string;
  username: string;
  role: UserRole;
  created_at: string;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  role: UserRole;
}

export interface UpdateUserRequest {
  password?: string;
  role?: UserRole;
}

export interface AuthStatus {
  has_users: boolean;
}

// Logs
export interface LogEntry {
  id: string;
  level: string;
  event: string;
  component: string;
  created_at: string;
  trace_id?: string;
  doc_id?: string;
  tenant_id?: string;
  user_id?: string;
  details?: Record<string, unknown>;
  error?: string;
}

export interface LogListResponse {
  logs: LogEntry[];
  total: number;
  page: number;
  per_page: number;
}

export interface LogListParams {
  level?: string;
  component?: string;
  trace_id?: string;
  doc_id?: string;
  start_time?: string;
  end_time?: string;
  page?: number;
  per_page?: number;
}

// API Keys
export interface ApiKeyEntry {
  id: string;
  key_prefix: string;
  tenant_id: string;
  tenant_name: string;
  rate_limit: number;
  enabled: boolean;
  created_at: string;
}

export interface CreateApiKeyRequest {
  tenant_id: string;
  tenant_name: string;
  rate_limit: number;
}

export interface CreateApiKeyResponse extends ApiKeyEntry {
  api_key: string;
}

export interface UpdateApiKeyRequest {
  tenant_name?: string;
  rate_limit?: number;
  enabled?: boolean;
}

// Billing & Usage
export interface UsageSummary {
  period_start: string;
  events: Record<string, number>;
}

export interface PlanLimits {
  ingest: number | null;
  search: number | null;
  graph_build: number | null;
}

export type PlanTier = "free" | "starter" | "pro";

export interface Plan {
  tier: PlanTier;
  name: string;
  price_cents: number;
  limits: PlanLimits;
}

export type SubscriptionStatus = "active" | "past_due" | "canceled";

export interface SubscriptionResponse {
  plan: Plan;
  status: SubscriptionStatus;
  current_period_start: string;
  updated_at: string | null;
}

export interface BillingConfig {
  enabled: boolean;
}

export interface CheckoutResponse {
  checkout_url: string;
  session_id: string;
}

export interface PortalResponse {
  portal_url: string;
}
