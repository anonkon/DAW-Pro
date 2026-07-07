-- DAWpro initial schema. See docs/plan/02-accounts-and-personas.md for rationale.
-- Apply with: supabase link && supabase db push  (or paste into the SQL editor)

create table if not exists personas (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  skill_level text not null check (skill_level in ('beginner', 'intermediate', 'advanced')),
  preferred_genres text[] not null default '{}',
  feedback_tone text not null default 'guided' check (feedback_tone in ('guided', 'direct', 'technical')),
  created_at timestamptz not null default now()
);

create table if not exists sessions (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references auth.users(id) on delete cascade,
  persona_id uuid not null references personas(id) on delete restrict,
  project_name text not null,
  reference_track_s3_key text,
  created_at timestamptz not null default now()
);

create table if not exists analysis_results (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references sessions(id) on delete cascade,
  job_id text not null,
  result jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists sessions_account_id_idx on sessions(account_id);
create index if not exists analysis_results_session_id_idx on analysis_results(session_id);

alter table personas enable row level security;
alter table sessions enable row level security;
alter table analysis_results enable row level security;

create policy "personas: owner full access" on personas
  for all using (account_id = auth.uid()) with check (account_id = auth.uid());

create policy "sessions: owner full access" on sessions
  for all using (account_id = auth.uid()) with check (account_id = auth.uid());

create policy "analysis_results: owner read via session" on analysis_results
  for select using (
    exists (
      select 1 from sessions
      where sessions.id = analysis_results.session_id
      and sessions.account_id = auth.uid()
    )
  );

-- Inserts to analysis_results come from the backend using the service role
-- key (which bypasses RLS), not directly from the dashboard client.
