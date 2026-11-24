export interface AppConfig {
  cognitoUserPoolId: string;
  cognitoClientId: string;
  apiBaseUrl: string;
  mockApi: boolean;
}

const env = import.meta.env;

export const config: AppConfig = {
  cognitoUserPoolId: env.VITE_COGNITO_USER_POOL_ID ?? "",
  cognitoClientId: env.VITE_COGNITO_CLIENT_ID ?? "",
  apiBaseUrl: (env.VITE_API_BASE_URL ?? "").replace(/\/$/, ""),
  mockApi: env.VITE_MOCK_API === "true",
};

export function missingRuntimeConfig(): string[] {
  const missing: string[] = [];
  if (!config.mockApi && !config.cognitoUserPoolId) missing.push("VITE_COGNITO_USER_POOL_ID");
  if (!config.mockApi && !config.cognitoClientId) missing.push("VITE_COGNITO_CLIENT_ID");
  if (!config.mockApi && !config.apiBaseUrl) missing.push("VITE_API_BASE_URL");
  return missing;
}
