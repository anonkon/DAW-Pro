import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { AnalysisResult, Session } from "@/lib/types";
import { SessionView } from "@/components/SessionView";

export default async function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: session } = await supabase
    .from("sessions")
    .select("*")
    .eq("id", id)
    .single();

  if (!session) notFound();

  const { data: latestResultRow } = await supabase
    .from("analysis_results")
    .select("result")
    .eq("session_id", id)
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  return (
    <SessionView
      session={session as Session}
      initialResult={(latestResultRow?.result as AnalysisResult) ?? null}
    />
  );
}
