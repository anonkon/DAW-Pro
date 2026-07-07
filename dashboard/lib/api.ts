import { createClient } from "./supabase/client";
import type { AnalyzeAccepted, AnalyzeSource, JobStatus } from "./types";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

async function authHeader(): Promise<HeadersInit> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}

export interface AnalyzeParams {
  file: File;
  sessionId: string;
  personaId: string;
  sonicIntention: string;
  source: AnalyzeSource;
  genre?: string;
  bpm?: number;
  timeSignature?: string;
}

export async function submitAnalysis(params: AnalyzeParams): Promise<AnalyzeAccepted> {
  const form = new FormData();
  form.set("file", params.file);
  form.set("session_id", params.sessionId);
  form.set("persona_id", params.personaId);
  form.set("sonic_intention", params.sonicIntention);
  form.set("source", params.source);
  if (params.genre) form.set("genre", params.genre);
  if (params.bpm) form.set("bpm", String(params.bpm));
  if (params.timeSignature) form.set("time_signature", params.timeSignature);

  const res = await fetch(`${BACKEND_URL}/analyze`, {
    method: "POST",
    headers: await authHeader(),
    body: form,
  });
  if (!res.ok) {
    throw new Error(`analyze request failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}

export async function fetchJobStatus(jobId: string): Promise<JobStatus> {
  const res = await fetch(`${BACKEND_URL}/jobs/${jobId}`, {
    headers: await authHeader(),
  });
  if (!res.ok) {
    throw new Error(`job status request failed: ${res.status} ${await res.text()}`);
  }
  return res.json();
}
