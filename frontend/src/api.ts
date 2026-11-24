import { getIdToken } from "./auth/cognito";
import { config } from "./config";

export interface JobSummary {
  job_id: string;
  title: string;
  status: "CREATED" | "JD_UPLOADED" | "JD_PARSED" | "FAILED";
  threshold: number;
  created_at: string;
  required_skills?: string[];
  jd_titles?: string[];
  required_years?: number | null;
}
export interface JobsResponse { jobs: JobSummary[]; }
export interface Candidate {
  job_id: string;
  candidate_id: string;
  status: "UPLOADED" | "PARSING" | "PARSED" | "SCORED" | "FAILED";
  source_key: string;
  file_name: string;
  name?: string | null;
  email?: string | null;
  skills?: string[];
  employers?: string[];
  titles?: string[];
  experience_years?: number | null;
  parsed_s3_key?: string | null;
  parser_version?: string;
  score?: number | null;
  above_threshold?: boolean | null;
  score_breakdown?: {
    skills?: { score: number; weight: number; matched?: string[]; missing?: string[] };
    title?: { score: number; weight: number; best_pair?: string[] | null };
    experience?: { score: number; weight: number; years_counted?: number | null; required_years?: number | null };
    scorer_version?: string;
  } | null;
  scored_at?: string | null;
  decision: "PENDING" | "SHORTLISTED" | "REJECTED";
  decision_history?: Array<{ action: string; by: string; at: string }>;
  email_status?: "NOT_SENT" | "SENT" | "FAILED" | "NO_EMAIL";
  created_at: string;
}
export interface CandidatesResponse { candidates: Candidate[]; counts: Record<string, number>; }
export interface FailedJob {
  failed_id: string; job_id: string; stage: string; s3_key: string;
  error_type: string; error_message: string; attempts?: number;
  message_id?: string | null; status: "OPEN" | "RETRIED" | "RESOLVED"; created_at: string;
}
export interface FailedJobsResponse { failed_jobs: FailedJob[]; }
export interface UploadUrl { file_name: string; url: string; s3_key: string; }
export interface CreateJobResponse { job: JobSummary; jd_upload?: UploadUrl; }
export interface UploadsResponse { uploads: UploadUrl[]; }

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message); this.name = "ApiError";
  }
}

const demoJob: JobSummary = {
  job_id: "a1b2c3d4e5f6", title: "Senior DevOps Engineer",
  status: "JD_PARSED", threshold: 60, created_at: "2026-11-20T09:30:00Z",
  required_skills: ["aws", "kubernetes", "terraform", "docker", "python"],
  jd_titles: ["senior devops engineer"], required_years: 5,
};
const demoCandidates: Candidate[] = [
  { job_id: demoJob.job_id, candidate_id: "1111111111111111", status: "SCORED", source_key: "resumes/demo/ava.pdf", file_name: "ava-morgan.pdf", name: "Ava Morgan", email: "ava.morgan@example.com", skills: ["aws","docker","kubernetes","terraform","python","linux"], employers: ["Northstar Cloud"], titles: ["senior devops engineer"], experience_years: 6, score: 95.5, above_threshold: true, score_breakdown: { skills:{score:1,weight:.5,matched:["aws","docker","kubernetes","terraform","python"],missing:[]}, title:{score:.91,weight:.3,best_pair:["senior devops engineer","senior devops engineer"]}, experience:{score:1,weight:.2,years_counted:6,required_years:5}, scorer_version:"1.0.0" }, decision:"PENDING", email_status:"NOT_SENT", created_at:"2026-11-20T09:42:00Z" },
  { job_id: demoJob.job_id, candidate_id: "2222222222222222", status: "SCORED", source_key: "resumes/demo/noah.pdf", file_name: "noah-patel.pdf", name: "Noah Patel", email: "noah.patel@example.com", skills: ["aws","docker","kubernetes","terraform","linux","prometheus"], employers: ["BluePeak Systems"], titles: ["devops engineer"], experience_years: 5, score: 87.2, above_threshold: true, score_breakdown: { skills:{score:.8,weight:.5,matched:["aws","docker","kubernetes","terraform"],missing:["python"]}, title:{score:.82,weight:.3,best_pair:["devops engineer","senior devops engineer"]}, experience:{score:1,weight:.2,years_counted:5,required_years:5}, scorer_version:"1.0.0" }, decision:"SHORTLISTED", email_status:"SENT", created_at:"2026-11-20T09:43:00Z" },
  { job_id: demoJob.job_id, candidate_id: "3333333333333333", status: "SCORED", source_key: "resumes/demo/mia.pdf", file_name: "mia-chen.pdf", name: "Mia Chen", email: "mia.chen@example.com", skills: ["aws","python","terraform","cloudformation"], employers: ["Meridian Tech"], titles: ["cloud engineer"], experience_years: 4, score: 72.8, above_threshold: true, score_breakdown: { skills:{score:.6,weight:.5,matched:["aws","terraform","python"],missing:["docker","kubernetes"]}, title:{score:.65,weight:.3,best_pair:["cloud engineer","senior devops engineer"]}, experience:{score:.8,weight:.2,years_counted:4,required_years:5}, scorer_version:"1.0.0" }, decision:"PENDING", email_status:"NOT_SENT", created_at:"2026-11-20T09:44:00Z" },
  { job_id: demoJob.job_id, candidate_id: "4444444444444444", status: "PARSING", source_key: "resumes/demo/ethan.docx", file_name: "ethan-brooks.docx", name: null, email: null, skills: [], employers: [], titles: [], experience_years: null, score: null, decision:"PENDING", email_status:"NOT_SENT", created_at:"2026-11-20T09:45:00Z" },
];
let mockJobs: JobSummary[] = [demoJob];
let mockCandidates: Candidate[] = [...demoCandidates];
let mockFailed: FailedJob[] = [{
  failed_id:"demo-failure-001", job_id:demoJob.job_id, stage:"PARSE", s3_key:"resumes/demo/corrupt-resume.docx",
  error_type:"CORRUPT_FILE", error_message:"The uploaded DOCX package could not be opened.", attempts:1,
  status:"OPEN", created_at:"2026-11-20T09:48:00Z",
}];

async function token(): Promise<string> {
  const value = await getIdToken();
  if (!value) throw new ApiError("Your recruiter session has expired. Sign in again.", 401);
  return value;
}
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (config.mockApi) return mockRequest<T>(path, init);
  const idToken = await token();
  const response = await fetch(`${config.apiBaseUrl}${path}`, {
    ...init,
    headers: { Accept:"application/json", ...(init.body ? {"Content-Type":"application/json"} : {}), ...init.headers, Authorization:idToken },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { error?:string; detail?:string };
    throw new ApiError(body.detail ?? body.error ?? `API request failed (${response.status}).`, response.status);
  }
  return response.json() as Promise<T>;
}
async function mockRequest<T>(path:string, init:RequestInit):Promise<T> {
  const method = init.method ?? "GET";
  if (path === "/jobs" && method === "GET") return {jobs:mockJobs} as T;
  if (path === "/jobs" && method === "POST") {
    const body = JSON.parse(String(init.body ?? "{}")) as {title:string;threshold:number};
    const job:JobSummary = {job_id:Math.random().toString(16).slice(2,14).padEnd(12,"0"),title:body.title,status:"JD_PARSED",threshold:body.threshold,created_at:new Date().toISOString(),required_skills:["aws","python"],jd_titles:[body.title.toLowerCase()],required_years:null};
    mockJobs = [job,...mockJobs]; return {job} as T;
  }
  const jobId = path.match(/^\/jobs\/([0-9a-f]{12})$/)?.[1];
  if (jobId && method === "GET") { const job=mockJobs.find(x=>x.job_id===jobId); if(!job) throw new ApiError("Job not found.",404); return job as T; }
  const candidatesMatch = path.match(/^\/jobs\/([0-9a-f]{12})\/candidates(?:\?decision=(PENDING|SHORTLISTED|REJECTED))?$/);
  if (candidatesMatch) { const rows=mockCandidates.filter(x=>x.job_id===candidatesMatch[1]); const counts={PENDING:rows.filter(x=>x.decision==="PENDING").length,SHORTLISTED:rows.filter(x=>x.decision==="SHORTLISTED").length,REJECTED:rows.filter(x=>x.decision==="REJECTED").length}; return {candidates:candidatesMatch[2]?rows.filter(x=>x.decision===candidatesMatch[2]):rows,counts} as T; }
  const detail=path.match(/^\/jobs\/([0-9a-f]{12})\/candidates\/([0-9a-f]{16})$/);
  if(detail){const row=mockCandidates.find(x=>x.job_id===detail[1]&&x.candidate_id===detail[2]);if(!row)throw new ApiError("Candidate not found.",404);return row as T;}
  if(path==="/failed-jobs") return {failed_jobs:mockFailed} as T;
  const retry=path.match(/^\/failed-jobs\/([^/]+)\/retry$/);
  if(retry){const row=mockFailed.find(x=>x.failed_id===retry[1]);if(!row)throw new ApiError("Failed job not found.",404);row.status="RETRIED";return row as T;}
  if(path.endsWith("/decision") && method==="POST"){const [jobId,candidateId]=path.split("/").filter(Boolean).slice(1,4);const row=mockCandidates.find(x=>x.job_id===jobId&&x.candidate_id===candidateId);if(!row)throw new ApiError("Candidate not found.",404);const body=JSON.parse(String(init.body??"{}")) as {action:string};row.decision=body.action==="shortlist"?"SHORTLISTED":"REJECTED";row.email_status=body.action==="shortlist"?(row.email?"SENT":"NO_EMAIL"):"NOT_SENT";return row as T;}
  throw new ApiError("No mock response is configured for this route.",501);
}
export const api = {
  listJobs: () => request<JobsResponse>("/jobs"),
  getJob: (jobId:string) => request<JobSummary>(`/jobs/${jobId}`),
  createJob: (body:{title:string;threshold:number;description_text?:string;jd_file_name?:string}) => request<CreateJobResponse>("/jobs",{method:"POST",body:JSON.stringify(body)}),
  createResumeUploads: (jobId:string,files:Array<{file_name:string;content_type:string}>) => request<UploadsResponse>(`/jobs/${jobId}/uploads`,{method:"POST",body:JSON.stringify({files})}),
  listCandidates: (jobId:string,decision?:string) => request<CandidatesResponse>(`/jobs/${jobId}/candidates${decision? `?decision=${decision}`:""}`),
  getCandidate: (jobId:string,candidateId:string) => request<Candidate>(`/jobs/${jobId}/candidates/${candidateId}`),
  decideCandidate: (jobId:string,candidateId:string,body:{action:"shortlist"|"reject";interview?:{date_time:string;location_or_link:string;notes?:string}}) => request<Candidate>(`/jobs/${jobId}/candidates/${candidateId}/decision`,{method:"POST",body:JSON.stringify(body)}),
  listFailedJobs: (jobId?:string) => request<FailedJobsResponse>(`/failed-jobs${jobId? `?job_id=${jobId}`:""}`),
  retryFailedJob: (failedId:string) => request<FailedJob>(`/failed-jobs/${failedId}/retry`,{method:"POST",body:"{}"}),
};
export async function uploadPresigned(url:string,file:File,onProgress:(percent:number)=>void):Promise<void>{
  if(config.mockApi){onProgress(100);return;}
  await new Promise<void>((resolve,reject)=>{
    const xhr=new XMLHttpRequest(); xhr.open("PUT",url); xhr.setRequestHeader("Content-Type",file.type);
    xhr.upload.onprogress=(event)=>{if(event.lengthComputable)onProgress(Math.round(event.loaded/event.total*100));};
    xhr.onload=()=>xhr.status>=200&&xhr.status<300?resolve():reject(new ApiError(`Upload failed (${xhr.status}). Check the file type and try again.`,xhr.status));
    xhr.onerror=()=>reject(new ApiError("Network error while uploading the file.",0));
    xhr.onabort=()=>reject(new ApiError("Upload was cancelled.",0)); xhr.send(file);
  });
}
export async function downloadShortlist(jobId:string):Promise<void>{
  if(config.mockApi){const rows=mockCandidates.filter(x=>x.job_id===jobId&&x.decision==="SHORTLISTED");const csv=["rank,name,email,score,skills_matched,skills_missing,titles,experience_years,decision,email_status",...rows.map((x,i)=>[i+1,x.name??"",x.email??"",x.score??"",x.score_breakdown?.skills?.matched?.join("; ")??"",x.score_breakdown?.skills?.missing?.join("; ")??"",x.titles?.join("; ")??"",x.experience_years??"",x.decision,x.email_status??""].map(v=>`"${String(v).replace(/"/g,'""')}"`).join(","))].join("\n");saveCsv(csv,jobId);return;}
  const idToken=await token();const response=await fetch(`${config.apiBaseUrl}/jobs/${jobId}/shortlist.csv`,{headers:{Authorization:idToken,Accept:"text/csv"}});
  if(!response.ok)throw new ApiError(`CSV export failed (${response.status}).`,response.status);
  saveCsv(await response.text(),jobId);
}
function saveCsv(csv:string,jobId:string){const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));const anchor=document.createElement("a");anchor.href=url;anchor.download=`shortlist-${jobId}.csv`;document.body.appendChild(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);}
