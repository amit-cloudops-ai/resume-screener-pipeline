# Recruiter frontend foundation — Phase A Step 5

React + Vite + TypeScript application. This establishes the build, Cognito SRP sign-in boundary, authenticated API client and local mock mode. It intentionally does not select the final dashboard visual direction; decision D16 reserves that approval for Step 6.

## Requirements and local setup

- Node.js 22+, npm 10+

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

The example enables `VITE_MOCK_API=true`. Mock mode returns an empty jobs list and makes no AWS requests.

For a configured environment set `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID` (app client must have no secret), `VITE_API_BASE_URL` (API Gateway base URL including `/v1`) and `VITE_MOCK_API=false`.

Authentication uses Cognito User Pool SRP per D5. The API client sends the raw Cognito ID token in `Authorization`, without a `Bearer ` prefix, per architecture and OpenAPI contracts. Do not log tokens or credentials.

## Commands

```bash
npm run typecheck
npm run build
npm run preview
```

## Security and scope

- Recruiters only; candidate login/portal is out of scope.
- No Cognito pool, user, client ID or API URL is provisioned by this frontend.
- No AWS resources are created and no deployment is performed.
- Never place secrets in `VITE_*` variables; Vite exposes these to the browser bundle.
- Mock mode is local-only and is not proof of authenticated API behaviour.
- The current shell is neutral. Final typography, palette, layout and dashboard composition await D16 approval in Step 6.
