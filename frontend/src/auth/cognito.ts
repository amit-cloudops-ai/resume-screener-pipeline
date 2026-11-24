import { AuthenticationDetails, CognitoUser, CognitoUserPool, CognitoUserSession } from "amazon-cognito-identity-js";
import { config } from "../config";

let pendingPasswordUser: CognitoUser | null = null;

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

export type SignInResult = "SIGNED_IN" | "NEW_PASSWORD_REQUIRED";
export function signIn(username: string, password: string): Promise<SignInResult> {
  if (config.mockApi) return Promise.resolve("SIGNED_IN");
  const user = new CognitoUser({ Username: username, Pool: getPool() });
  const details = new AuthenticationDetails({ Username: username, Password: password });
  return new Promise((resolve, reject) => user.authenticateUser(details, {
    onSuccess: () => { pendingPasswordUser = null; resolve("SIGNED_IN"); },
    onFailure: (error) => reject(error),
    newPasswordRequired: () => { pendingPasswordUser = user; resolve("NEW_PASSWORD_REQUIRED"); },
    mfaRequired: () => reject(new Error("MFA is required but this frontend flow is not configured yet.")),
    totpRequired: () => reject(new Error("TOTP is required but this frontend flow is not configured yet.")),
  }));
}

export function completeNewPassword(newPassword: string): Promise<void> {
  if (!pendingPasswordUser) return Promise.reject(new Error("There is no pending password challenge."));
  const user = pendingPasswordUser;
  return new Promise((resolve, reject) => user.completeNewPasswordChallenge(newPassword, {}, {
    onSuccess: () => { pendingPasswordUser = null; resolve(); },
    onFailure: (error) => reject(error),
  }));
}

export function signOut(): void {
  pendingPasswordUser = null;
  if (!config.mockApi) getCurrentUser()?.signOut();
}
export function hasCognitoConfiguration(): boolean { return Boolean(config.cognitoUserPoolId && config.cognitoClientId); }
