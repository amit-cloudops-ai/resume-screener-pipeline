import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api } from "./api";
import type { JobSummary } from "./api";
import { hasCognitoConfiguration, signIn, signOut } from "./auth/cognito";
import { config, missingRuntimeConfig } from "./config";

export default function App() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [signedIn, setSignedIn] = useState(config.mockApi);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!signedIn) return;
    let active = true;
    setLoading(true);
    api.listJobs().then((result) => { if (active) setJobs(result.jobs); })
      .catch((reason: unknown) => { if (active) setError(reason instanceof Error ? reason.message : "Unable to load recruiter jobs."); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [signedIn]);

  async function handleSignIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setLoading(true);
    try { await signIn(username.trim(), password); setSignedIn(true); setPassword(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Sign-in failed."); }
    finally { setLoading(false); }
  }
  function handleSignOut() { signOut(); setSignedIn(false); setJobs([]); }

  const missing = missingRuntimeConfig();
  if (!signedIn) return (
    <main className="app-shell"><section className="auth-panel" aria-labelledby="login-title">
      <p className="eyebrow">RECRUITER WORKSPACE</p><h1 id="login-title">Sign in</h1>
      <p className="muted">Use the recruiter account provisioned by the administrator.</p>
      {!hasCognitoConfiguration() && !config.mockApi && <p className="notice" role="status">Cognito configuration is not available in this environment.</p>}
      <form onSubmit={handleSignIn}>
        <label htmlFor="username">Email</label><input id="username" type="email" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
        <label htmlFor="password">Password</label><input id="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={loading || (!config.mockApi && !hasCognitoConfiguration())}>{loading ? "Signing in…" : "Sign in"}</button>
      </form>
      {config.mockApi && <p className="notice">Mock mode is enabled. No AWS authentication or API request is made.</p>}
    </section></main>
  );

  return (
    <main className="app-shell">
      <header className="workspace-header"><div><p className="eyebrow">RECRUITER WORKSPACE</p><h1>Resume Screener</h1></div><button className="secondary" type="button" onClick={handleSignOut}>Sign out</button></header>
      {missing.length > 0 && <p className="notice">Runtime configuration required: {missing.join(", ")}</p>}
      {error && <p className="error" role="alert">{error}</p>}
      <section aria-labelledby="jobs-title">
        <div className="section-heading"><div><p className="eyebrow">PIPELINE OVERVIEW</p><h2 id="jobs-title">Your jobs</h2></div><span className="muted">{jobs.length} jobs</span></div>
        {loading ? <p className="muted">Loading jobs…</p> : jobs.length === 0 ? <div className="empty-state"><h3>No jobs yet</h3><p className="muted">Job creation and candidate workflows will follow the approved dashboard direction.</p></div> :
          <ul className="job-list">{jobs.map((job) => <li key={job.job_id}><strong>{job.title}</strong><span>{job.status}</span></li>)}</ul>}
      </section>
      {config.mockApi && <p className="notice">Local mock mode — data is not connected to AWS.</p>}
    </main>
  );
}
