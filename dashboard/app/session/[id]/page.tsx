import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { AnalysisResult, Session } from "@/lib/types";
import { SessionView } from "@/components/SessionView";
import { SideNav, type HistoryEntry } from "@/components/SideNav";

export default async function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: session } = await supabase
    .from("sessions")
    .select("*")
    .eq("id", id)
    .single();

  if (!session) notFound();

  // One round trip for the page and the nav together: the same rows provide
  // both the latest result and the history list.
  const [{ data: resultRows }, { data: sessions }] = await Promise.all([
    supabase
      .from("analysis_results")
      .select("job_id, created_at, result")
      .eq("session_id", id)
      .order("created_at", { ascending: false })
      .limit(20),
    supabase.from("sessions").select("*").order("created_at", { ascending: false }),
  ]);

  const rows = resultRows ?? [];
  const latestResult = (rows[0]?.result as AnalysisResult) ?? null;

  // The newest analysis is what the page renders, so history is everything else.
  const history: HistoryEntry[] = rows.slice(1).map((row) => ({
    job_id: row.job_id as string,
    created_at: row.created_at as string,
    summary: (row.result as AnalysisResult | null)?.summary ?? null,
  }));

  return (
    <SessionView
      session={session as Session}
      initialResult={latestResult}
      nav={
        <SideNav
          sessions={(sessions as Session[]) ?? []}
          currentSessionId={id}
          history={history}
          tempoBpm={latestResult?.measurements?.tempo_bpm ?? null}
        />
      }
    />
  );
}
