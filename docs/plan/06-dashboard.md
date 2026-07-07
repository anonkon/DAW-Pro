# The Dashboard — Next.js

Referenced from [[00-overview]] decisions 4, 9. Consumes the schema in [[01-json-contract]], auths per [[02-accounts-and-personas]], talks to the backend in [[04-backend-engine]].

## Stack

Next.js (App Router) + TypeScript, Tailwind CSS for styling, WaveSurfer.js for waveform rendering. Dark theme, matching the poster's mockup screenshot.

## Routes

```
/login                     Supabase Auth (email + password)
/dashboard                 Session list + "new session" + persona picker/creator
/session/[id]              Main analysis view
```

## `/session/[id]` — main view

- **Waveform panel** — WaveSurfer.js rendering of the project audio (captured from plugin or uploaded), with region markers plotted at `AnalysisResult.timing_markers[].time_sec`, colored by `severity`.
- **Comparative EQ panel** — bar/curve chart of `AnalysisResult.eq_comparison` (5 fixed bands, project vs. reference `_db` per band — no client-side FFT needed, the backend already reduced this to a fixed small array per [[01-json-contract]]).
- **Chat panel** — renders `AnalysisResult.summary` and the `issues[]` list as chat-bubble-style messages, consistent with the poster's "chat bubble" element and the mentor framing (guidance, not commands).
- **"Upload reference track" control** — direct file upload, hits `/analyze` with `source: "reference_upload"`.
- **Status/progress indicator** — driven by the polling hook below, shown while a job is in flight.

## Polling implementation

```ts
function usePollJob(jobId: string | null) {
  const [status, setStatus] = useState<JobStatus | null>(null);
  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      const res = await fetch(`${BACKEND_URL}/jobs/${jobId}`);
      const data: JobStatus = await res.json();
      setStatus(data);
      if (data.status === "done" || data.status === "failed") clearInterval(interval);
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId]);
  return status;
}
```

Plain `setInterval` + `fetch`, cleaned up on unmount/job completion — no websocket connection lifecycle to manage, consistent with [[00-overview]] decision 9.

## Auth

`supabase-js` client-side, session persisted via cookies (Next.js middleware redirects unauthenticated requests to `/login`). Every fetch to the FastAPI backend attaches the Supabase JWT in an `Authorization` header; the backend verifies it server-side to recover `account_id` rather than trusting a client-supplied value (see [[02-accounts-and-personas]]).

## Persona picker

Simple dropdown + "manage personas" modal on `/dashboard`, backed directly by Supabase (`supabase-js` `from("personas")` CRUD) — no FastAPI involvement needed, since this is plain relational CRUD with RLS already enforcing per-account access (see [[02-accounts-and-personas]]).

## What's explicitly out of scope

- Mobile-responsive layout — desktop-only is fine for a demo/dashboard used alongside a DAW.
- Real-time collaborative sessions (multiple users viewing the same session live) — single-viewer only.
