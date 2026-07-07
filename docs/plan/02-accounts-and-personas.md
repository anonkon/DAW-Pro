# Accounts & Personas

Referenced from [[00-overview]] decision 4. Backs the auth flow in [[06-dashboard]] and the prompt personalization in [[05-ai-brain]].

## Why full accounts (not anonymous sessions)

Explicit user requirement: accounts should support multiple accounts and multiple saved personas per account — this isn't just "who's logged in," it's a personalization axis for the AI mentor. A bedroom-producer persona and a "I mix professionally, be terse" persona on the same account should get different Gemini prompting.

## Data model (Supabase / Postgres)

```sql
-- Supabase Auth provides `auth.users` (id, email, ...) out of the box — no custom accounts table needed.

create table personas (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references auth.users(id) on delete cascade,
  name text not null,                       -- e.g. "Trap - Learning EQ"
  skill_level text not null,                -- 'beginner' | 'intermediate' | 'advanced'
  preferred_genres text[] not null default '{}',
  feedback_tone text not null default 'guided',  -- 'guided' | 'direct' | 'technical'
  created_at timestamptz not null default now()
);

create table sessions (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references auth.users(id) on delete cascade,
  persona_id uuid not null references personas(id) on delete restrict,
  project_name text not null,
  reference_track_s3_key text,              -- nullable until a reference is uploaded
  created_at timestamptz not null default now()
);

create table analysis_results (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  job_id text not null,                     -- correlates to backend in-memory job id
  result jsonb not null,                    -- the AnalysisResult from 01-json-contract.md
  created_at timestamptz not null default now()
);
```

Row-Level Security: enable RLS on all three tables, policy `account_id = auth.uid()` for `personas`/`sessions`, and a join-based policy on `analysis_results` (via `sessions.account_id`). This is a couple of `create policy` statements — not optional, since Supabase tables are exposed directly to the client via `supabase-js` in the dashboard.

## How personas feed the AI

`persona_id` is required on every `POST /analyze` call ([[01-json-contract]]). The backend fetches the persona row and folds `skill_level`, `preferred_genres`, and `feedback_tone` into the Gemini system prompt (see [[05-ai-brain]] for the exact template) — e.g. a `beginner` + `guided` persona gets more explanatory, exploration-oriented language; an `advanced` + `direct` persona gets terser, more technical phrasing, still without prescriptive fixes (that guardrail is non-negotiable per the poster's stated philosophy, regardless of persona).

## Auth flow (dashboard-side)

Supabase Auth handles signup/login (email+password is sufficient — no need for OAuth providers at this scope). `supabase-js` client in the Next.js app manages the session cookie; every API call from the dashboard to the FastAPI backend carries the Supabase JWT, which the backend verifies (via Supabase's JWT secret) to recover `account_id` server-side rather than trusting a client-supplied one.

## What's explicitly out of scope

- Password reset / email verification flows — Supabase Auth defaults are fine, no custom UI needed beyond what `supabase-js` provides.
- Role-based permissions (admin/user tiers) — single-tier accounts only.
