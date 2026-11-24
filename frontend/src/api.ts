import { getIdToken } from "./auth/cognito";
import { config } from "./config";

export interface JobSummary {
  job_id: string; title: string;
  status: "CREATED" | "JD_UPLOADED" | "JD_PARSED" | "FAILED";
  threshold: number; created_at: string;
}
export interface JobsResponse { jobs: JobSummary[]; }
export class ApiError extends Error {
  constructor(message: string, public readonly status: number) { super(message); this.name = "ApiError"; }
}
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (config.mockApi) {
    if (path === "/jobs") return { jobs: [] } as T;
    throw new ApiError("No mock response is configured for this route.", 501);
  }
  const token = await getIdToken();
  if (!token) throw new ApiError("Your recruiter session has expired. Sign in again.", 401);
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
      // API contract expects the raw Cognito ID token, without a Bearer prefix.
      Authorization: token,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { error?: string; detail?: string };
    throw new ApiError(body.detail ?? body.error ?? `API request failed (${response.status}).`, response.status);
  }
  return response.json() as Promise<T>;
}
export const api = { listJobs: () => request<JobsResponse>("/jobs") };
