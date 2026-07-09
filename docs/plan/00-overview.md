# DAWpro — Architecture Overview & Decision Log

Project P37, Coding Fest 2026, University of Sydney. Source poster: `coding-fest-2026_poster-template_final (1).pdf (1).pdf`.

DAWpro is an interactive VST plugin that mentors self-taught music producers: it captures audio/metadata from inside a DAW, compares it against a reference track using AI, and surfaces contextual (not prescriptive) mixing feedback in a web dashboard.

## System diagram

```
┌─────────────────────┐
│  JUCE VST3 Plugin    │  "The Bridge" — lives on the master bus in the DAW
│  (C++, CMake)        │  Continuous rolling-buffer capture of audio + metadata
└──────────┬───────────┘  Explicit "Analyze" trigger → snapshot + POST
           │ multipart POST (audio + BPM/time-sig)
           ▼
┌─────────────────────┐
│  FastAPI Backend     │  "The Engine" — local-only, runs on the demo machine
│  (Python)            │  Demucs v4 (htdemucs) stem separation
│                       │  Librosa feature extraction
└──────────┬───────────┘
           │ features JSON + persona + intention
           ▼
┌─────────────────────┐
│  LangChain + Gemini   │  "The Brain" — Google AI Studio API
│  2.5 Pro              │  Structured JSON diagnosis, persona-aware
└──────────┬───────────┘
           │ AnalysisResult JSON
           ▼
┌─────────────────────┐
│  Next.js Dashboard    │  "The Dashboard" — Tailwind + WaveSurfer.js
│  (TypeScript)         │  Polls job status, renders EQ curves / timing grid / chat
└──────────────────────┘

Supabase: accounts, personas, sessions, analysis results (relational/queryable data)
AWS S3:   uploaded reference tracks, captured audio, Demucs stem output (binary blobs)
```

## Repo layout (monorepo)

```
DAW-Pro/
  plugin/       JUCE C++ VST3 source + CMakeLists.txt
  backend/      FastAPI app, Demucs/Librosa pipeline, LangChain/Gemini chain
  dashboard/    Next.js app
  docs/plan/    This planning doc set
```

## Decision log

Each decision below was made deliberately (via `/grill-me`) — read the "why" before changing any of these, since later docs assume them.

1. **Full poster scope**, not a trimmed hackathon MVP. All four layers (plugin, backend, AI, dashboard) plus S3 and Supabase get built.
   *Why:* explicit user directive — "whatever is in the submission artifact, that's what we have to make."

2. **Continuous capture, explicit-trigger send.** The plugin passively buffers master-bus audio + metadata on a rolling basis the whole time the DAW plays (satisfies "silently capturing... without disrupting workflow"). Sending that buffer to the backend for analysis is a manual click ("Analyze" button), not a live stream.
   *Why:* Demucs/Librosa/Gemini are batch operations (seconds-to-minutes), not real-time — a continuous stream to the AI would have nothing to consume it. Explicit-trigger avoids building a streaming protocol, backpressure handling, and partial-buffer edge cases for no benefit.
   *How to apply:* see [[03-plugin-bridge]] for the ring-buffer design.

3. **Local-only backend**, no cloud deployment.
   *Why:* Demucs is CPU/GPU-heavy; deploying it behind a fast endpoint needs a GPU box, which is a whole infra axis that buys nothing for a live demo where the presenter controls the machine. Confirmed by user: "local on prem."
   *How to apply:* FastAPI and Next.js both run on `localhost` during development and demo. Deployment is an explicit future step, not assumed.

4. **Full Supabase Auth accounts with multi-persona support**, not anonymous sessions.
   *Why:* explicit user requirement — accounts should support multiple saved personas (skill level, preferred genres, mentorship tone) that shape how Gemini mentors that session.
   *How to apply:* see [[02-accounts-and-personas]] for the schema and how personas feed the Gemini prompt.

5. **Storage split: Supabase for relational data, Cloudflare R2 for binary blobs.**
   *Why:* accounts/personas/sessions/results are queryable structured data that belongs in Postgres; audio files (uploads, captures, stems) are large binaries that don't belong in a DB row. Confirmed by user.
   *Amended:* originally AWS S3 (matching the poster), swapped to Cloudflare R2 - same role (S3-API-compatible object storage), no AWS account needed, zero egress fees.
   *How to apply:* Supabase rows reference R2 objects by key/URL, never store audio inline. See [[07-infra-storage]].

6. **Gemini via Google AI Studio API key**, not Vertex AI.
   *Why:* AI Studio gives a working API key in ~2 minutes with no GCP project/billing/IAM setup. Vertex AI's enterprise features (VPC controls, quota mgmt, regional residency) have no use case here.
   *How to apply:* `GEMINI_API_KEY` env var, `langchain-google-genai`'s `ChatGoogleGenerativeAI`. See [[05-ai-brain]].

7. **Demucs `htdemucs`** (base v4 model), not `htdemucs_ft`.
   *Why:* stems feed Librosa feature extraction for AI reasoning about balance/clashes, not for a human to listen to in isolation — separation cleanliness matters less than speed here. `_ft` is ~4x slower for marginal analytical benefit.

8. **Monorepo** under the already-created `anonkon/DAW-Pro` GitHub repo.
   *Why:* three toolchains (C++/CMake, Python, TypeScript) built by 1-2 people on a tight timeline — repo-hopping adds friction, not isolation value.

9. **Dashboard uses REST + polling**, not websockets.
   *Why:* analysis is a single batch job (10-60+ seconds), not a continuous stream of updates. `POST /analyze` returns a `job_id` immediately; dashboard polls `GET /jobs/{job_id}` every ~2s. Gets "feels alive" progress UX without websocket connection-lifecycle complexity.
   *How to apply:* see [[01-json-contract]] for the job status shape and [[04-backend-engine]] for the in-memory job store.

## Build order

Backend + AI first, plugin last — the plugin is the highest-risk, most manually-tested layer (no audio hardware/DAW in Claude's environment; the user drives all compiling and in-DAW testing). Everything upstream of the plugin can be validated with `curl`/file uploads before any C++ is written.

1. [[01-json-contract]] — schema all other layers build against
2. [[02-accounts-and-personas]] + [[07-infra-storage]] — data model (parallel)
3. [[04-backend-engine]] — Demucs + Librosa pipeline
4. [[05-ai-brain]] — Gemini/LangChain chain
5. [[06-dashboard]] — Next.js UI (parallel with 3-4 once contract is fixed)
6. [[03-plugin-bridge]] — JUCE VST3 plugin
7. End-to-end integration test + demo polish
