export const config = {
  cognitoUserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID ?? "",
  cognitoClientId: import.meta.env.VITE_COGNITO_CLIENT_ID ?? "",
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, ""),
  mockApi: import.meta.env.VITE_MOCK_API === "true",
};
export function missingRuntimeConfig(): string[] {
  const missing: string[] = [];
  if (!config.mockApi && !config.cognitoUserPoolId) missing.push("VITE_COGNITO_USER_POOL_ID");
  if (!config.mockApi && !config.cognitoClientId) missing.push("VITE_COGNITO_CLIENT_ID");
  if (!config.mockApi && !config.apiBaseUrl) missing.push("VITE_API_BASE_URL");
  return missing;
}
