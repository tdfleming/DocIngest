import client from "./client";
import type {
  AuthStatus,
  CreateUserRequest,
  LoginResponse,
  UpdateUserRequest,
  UserResponse,
} from "./types";

export async function login(
  username: string,
  password: string
): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>("/auth/login", {
    username,
    password,
  });
  return data;
}

export async function bootstrap(
  username: string,
  password: string
): Promise<LoginResponse> {
  const { data } = await client.post<LoginResponse>("/auth/bootstrap", {
    username,
    password,
    role: "admin",
  });
  return data;
}

export async function getMe(): Promise<UserResponse> {
  const { data } = await client.get<UserResponse>("/auth/me");
  return data;
}

export async function getAuthStatus(): Promise<AuthStatus> {
  const { data } = await client.get<AuthStatus>("/auth/status");
  return data;
}

export async function listUsers(): Promise<UserResponse[]> {
  const { data } = await client.get<UserResponse[]>("/auth/users");
  return data;
}

export async function createUser(
  request: CreateUserRequest
): Promise<UserResponse> {
  const { data } = await client.post<UserResponse>("/auth/users", request);
  return data;
}

export async function updateUser(
  userId: string,
  request: UpdateUserRequest
): Promise<UserResponse> {
  const { data } = await client.patch<UserResponse>(
    `/auth/users/${userId}`,
    request
  );
  return data;
}

export async function deleteUser(
  userId: string
): Promise<{ id: string; status: string }> {
  const { data } = await client.delete(`/auth/users/${userId}`);
  return data;
}
