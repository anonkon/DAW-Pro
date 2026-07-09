# Infra & Storage — Supabase + Cloudflare R2

Referenced from [[00-overview]] decision 5. Schema detail for [[02-accounts-and-personas]]; consumed by [[04-backend-engine]] during the `queued` pipeline stage.

**Amended from the original AWS S3 plan** — swapped to Cloudflare R2, which speaks the same S3 API (boto3 works unchanged, just pointed at a different endpoint), has zero egress fees, and doesn't need a separate AWS account. Functionally identical role in the architecture: binary blob storage, referenced by key from Supabase rows.

## The split

**Supabase (Postgres)** holds everything relational/queryable: accounts (via Supabase Auth), personas, sessions, analysis results as JSONB. **Cloudflare R2** holds everything binary: uploaded reference tracks, captured master-bus WAV snapshots, Demucs stem output. Supabase rows reference R2 objects by key, never store audio inline — audio doesn't belong in a DB row.

## R2 bucket layout

```
r2://dawpro-{env}/
  {account_id}/{session_id}/reference.wav
  {account_id}/{session_id}/capture-{job_id}.wav
  {account_id}/{session_id}/stems/{job_id}/drums.wav
  {account_id}/{session_id}/stems/{job_id}/bass.wav
  {account_id}/{session_id}/stems/{job_id}/vocals.wav
  {account_id}/{session_id}/stems/{job_id}/other.wav
```

Keyed by `account_id`/`session_id` so per-account scoping is straightforward if this ever moves beyond a single local demo user.

## Upload/download flow

Backend uploads directly via `boto3` (`put_object`/`upload_file`, `endpoint_url` pointed at `https://{account_id}.r2.cloudflarestorage.com`) during the `queued` stage — the plugin/dashboard POST audio to FastAPI first, FastAPI is what talks to R2, not the client directly. This keeps R2 credentials server-side only (never shipped to the plugin binary or the dashboard's client-side JS).

If the dashboard ever needs to let a user re-download a stem or the original reference track, generate a **presigned URL** (`boto3`'s `generate_presigned_url` works against R2 the same as S3, short expiry e.g. 15 min) on demand rather than making the bucket public or proxying bytes through FastAPI.

## R2 setup (what to actually click)

1. Cloudflare dashboard → **R2 Object Storage** → **Create bucket** (any name, e.g. `dawpro-dev`). R2 has a free tier (10GB storage, no egress fees) - no billing setup required to get started.
2. **R2 → Manage API tokens → Create API token**. Scope it to **Object Read & Write**, restricted to the one bucket you just created (not account-wide). This gives you an **Access Key ID** and **Secret Access Key** - shown once, copy both immediately.
3. Your **Account ID** is shown on the R2 overview page (also in the right sidebar of the main Cloudflare dashboard) - it's what builds the endpoint URL, not a separate credential to generate.
4. Fill into `backend/.env`: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`.

No IAM policy JSON to write by hand (unlike AWS) - the API token creation flow scopes permissions directly.

## Supabase schema

See [[02-accounts-and-personas]] for full DDL (`personas`, `sessions`, `analysis_results` tables, RLS policies). `auth.users` is Supabase Auth's built-in table — no custom `accounts` table needed.

## Local dev credentials

`.env` (gitignored, never committed): `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (backend uses the service key to bypass RLS when writing on the user's behalf after verifying their JWT; the dashboard uses the public anon key + RLS for direct Supabase access), `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`.

Add to root `.gitignore`: `.env`, `.env.local`, `**/node_modules/`, `**/__pycache__/`, `**/*.pyc`, `plugin/build/`, `dashboard/.next/`.
