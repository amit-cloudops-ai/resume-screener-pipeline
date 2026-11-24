import { AuthenticationDetails, CognitoUser, CognitoUserPool, CognitoUserSession } from "amazon-cognito-identity-js";
import { config } from "../config";

function getPool(): CognitoUserPool {
  if (!config.cognitoUserPoolId || !config.cognitoClientId) throw new Error("Cognito is not configured. Set VITE_COGNITO_* environment variables.");
  return new CognitoUserPool({ UserPoolId: config.cognitoUserPoolId, ClientId: config.cognitoClientId });
}
function getCurrentUser(): CognitoUser | null { return getPool().getCurrentUser(); }

export function getIdToken(): Promise<string | null> {
  if (config.mockApi) return Promise.resolve("local-mock-id-token");
  const user = getCurrentUser();
  if (!user) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    user.getSession((error: Error | null, session: CognitoUserSession | null) => {
      if (error) return reject(error);
      if (!session?.isValid()) return resolve(null);
      resolve(session.getIdToken().getJwtToken());
    });
  });
}

export function signIn(username: string, password: string): Promise<void> {
  if (config.mockApi) return Promise.resolve();
  const user = new CognitoUser({ Username: username, Pool: getPool() });
  const details = new AuthenticationDetails({ Username: username, Password: password });
  return new Promise((resolve, reject) => user.authenticateUser(details, {
    onSuccess: () => resolve(),
    onFailure: (error) => reject(error),
    newPasswordRequired: () => reject(new Error("A temporary password must be changed before continuing.")),
    mfaRequired: () => reject(new Error("MFA is required but this frontend flow is not configured yet.")),
    totpRequired: () => reject(new Error("TOTP is required but this frontend flow is not configured yet.")),
  }));
}
export function signOut(): void { if (!config.mockApi) getCurrentUser()?.signOut(); }
export function hasCognitoConfiguration(): boolean { return Boolean(config.cognitoUserPoolId && config.cognitoClientId); }
