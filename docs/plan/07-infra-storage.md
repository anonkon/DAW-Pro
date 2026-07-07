# Infra & Storage — Supabase + S3

Referenced from [[00-overview]] decision 5. Schema detail for [[02-accounts-and-personas]]; consumed by [[04-backend-engine]] during the `queued` pipeline stage.

## The split

**Supabase (Postgres)** holds everything relational/queryable: accounts (via Supabase Auth), personas, sessions, analysis results as JSONB. **AWS S3** holds everything binary: uploaded reference tracks, captured master-bus WAV snapshots, Demucs stem output. Supabase rows reference S3 objects by key, never store audio inline — audio doesn't belong in a DB row, and S3 is the standard place for it regardless of what's managing the database.

## S3 bucket layout

```
s3://dawpro-{env}/
  {account_id}/{session_id}/reference.wav
  {account_id}/{session_id}/capture-{job_id}.wav
  {account_id}/{session_id}/stems/{job_id}/drums.wav
  {account_id}/{session_id}/stems/{job_id}/bass.wav
  {account_id}/{session_id}/stems/{job_id}/vocals.wav
  {account_id}/{session_id}/stems/{job_id}/other.wav
```

Keyed by `account_id`/`session_id` so a bucket-level IAM policy can (later) scope access per-account if this ever moves beyond a single local demo user.

## Upload/download flow

Backend uploads directly via `boto3` (`put_object`) during the `queued` stage — the plugin/dashboard POST audio to FastAPI first, FastAPI is what talks to S3, not the client directly. This keeps AWS credentials server-side only (never shipped to the plugin binary or the dashboard's client-side JS).

If the dashboard ever needs to let a user re-download a stem or the original reference track, generate a **presigned URL** (`boto3`'s `generate_presigned_url`, short expiry e.g. 15 min) on demand rather than making the bucket public or proxying bytes through FastAPI.

## IAM

A single IAM user (or role) scoped to one policy: `s3:PutObject`, `s3:GetObject` on `arn:aws:s3:::dawpro-{env}/*` only. No broader account access needed — this is audio file storage, not a general-purpose AWS footprint.

## Supabase schema

See [[02-accounts-and-personas]] for full DDL (`personas`, `sessions`, `analysis_results` tables, RLS policies). `auth.users` is Supabase Auth's built-in table — no custom `accounts` table needed.

## Local dev credentials

`.env` (gitignored, never committed): `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (backend uses the service key to bypass RLS when writing on the user's behalf after verifying their JWT; the dashboard uses the public anon key + RLS for direct Supabase access), `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`.

Add to root `.gitignore`: `.env`, `.env.local`, `**/node_modules/`, `**/__pycache__/`, `**/*.pyc`, `plugin/build/`, `dashboard/.next/`.
