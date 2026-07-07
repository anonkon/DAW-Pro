# The Engine — FastAPI Backend

Referenced from [[00-overview]] decisions 3, 5, 7, 9. Consumes uploads from [[03-plugin-bridge]] and the dashboard's reference-track upload, produces the `AnalysisResult` defined in [[01-json-contract]] by calling the chain in [[05-ai-brain]], and persists via [[07-infra-storage]].

## Why local-only

Demucs is CPU/GPU-heavy; a fast deployed endpoint needs a GPU box, which is a whole infra axis with no payoff for a live demo where the presenter controls the machine (confirmed: "local on prem"). The backend runs as `uvicorn app.main:app` on the demo machine, `localhost:8000`.

## Endpoints

```
POST /analyze          multipart: AnalyzeRequest fields + WAV file → AnalyzeAccepted {job_id}
GET  /jobs/{job_id}    → JobStatus (polled by dashboard every ~2s)
POST /personas         create a persona (or handled directly by dashboard→Supabase, see note below)
GET  /health           trivial liveness check, useful while wiring the plugin's HTTP client
```

Note: persona/session CRUD could go directly from the dashboard to Supabase via `supabase-js` without touching FastAPI at all, since Supabase exposes a REST/Postgrest API natively. **Recommendation: do that** — only put `/analyze` and `/jobs/{id}` on FastAPI, since those are the only endpoints with real backend logic (Demucs/Librosa/Gemini). Keeps the backend focused on the audio pipeline, not CRUD.

## Job execution model

**In-memory dict** (`dict[str, JobStatus]`) as the job store, background execution via FastAPI's `BackgroundTasks` (or a plain `asyncio.create_task` if steps need to be `await`-able around blocking calls run in a thread pool via `asyncio.to_thread`).

*Why not Celery/Redis/a real task queue:* single-process local demo, one user driving it at a time. A task queue is infrastructure for concurrent multi-worker scaling, which doesn't exist here — it would be pure overhead. This is an explicit place to revisit if DAWpro ever needs multi-user concurrent analysis.

## Pipeline stages (drives the `JobStatus.status` enum from [[01-json-contract]])

1. **`queued`** → job created, file saved to a temp path + uploaded to S3 (per [[07-infra-storage]]).
2. **`separating_stems`** → run Demucs `htdemucs` (via the `demucs` Python package's API, not shelling out, for cleaner error handling) on the uploaded audio. Produces drums/bass/vocals/other stems.
3. **`extracting_features`** → run Librosa on the full mix and each stem:
   - RMS energy envelope (overall loudness over time)
   - Spectral centroid + a 5-band frequency-energy breakdown (feeds `AnalysisResult.eq_comparison`)
   - Onset/transient detection (`librosa.onset.onset_detect`) (feeds `AnalysisResult.timing_markers`)
   Same extraction runs on the reference track (cached per-session after first upload — no need to re-run Demucs/Librosa on the reference track for every subsequent analysis in that session).
4. **`analyzing`** → assembled features + persona + sonic intention passed to the LangChain/Gemini chain ([[05-ai-brain]]).
5. **`done`** → `AnalysisResult` written to `job_store[job_id]` and persisted to Supabase's `analysis_results` table; dashboard's next poll picks it up.
6. **`failed`** → any exception in stages 2-4 sets `status="failed"` with `error` populated, rather than leaving the dashboard polling forever.

## Why `htdemucs` (not `htdemucs_ft`)

Stems feed feature extraction for AI reasoning about balance/clashes, not direct human listening — separation cleanliness matters less than turnaround speed here (`_ft` is ~4x slower for a few minutes of audio).

## Key dependencies

```
fastapi, uvicorn, python-multipart
demucs, librosa, soundfile, numpy
langchain, langchain-google-genai
supabase-py, boto3
pydantic
```

## Config / secrets

`.env` (gitignored): `GEMINI_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`.
