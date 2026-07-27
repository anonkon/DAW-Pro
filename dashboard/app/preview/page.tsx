/* Design preview: renders SessionView against a fixture captured from a real
 * pipeline run (dashboard/lib/fixture.json), with no auth and no Supabase.
 *
 * This exists so the charts can be looked at while iterating on them - the
 * validator checks colour, not layout. Delete it, along with the fixture, once
 * the design has settled. */
import fixture from "@/lib/fixture.json";
import type { AnalysisResult, Session } from "@/lib/types";
import { SessionView } from "@/components/SessionView";
import { SideNav } from "@/components/SideNav";

const session: Session = {
  id: "preview",
  account_id: "preview",
  persona_id: "preview",
  project_name: "Neon Pulse",
  reference_track_s3_key: null,
  created_at: new Date().toISOString(),
};

const otherSessions: Session[] = [
  session,
  { ...session, id: "s2", project_name: "Midnight Drive" },
  { ...session, id: "s3", project_name: "Static Bloom" },
];

export default function PreviewPage() {
  const result = fixture as unknown as AnalysisResult;
  return (
    <SessionView
      session={session}
      initialResult={result}
      nav={
        <SideNav
          sessions={otherSessions}
          currentSessionId={session.id}
          tempoBpm={result.measurements?.tempo_bpm ?? null}
          history={[
            {
              job_id: "h1",
              created_at: new Date(Date.now() - 36e5).toISOString(),
              summary: "Low end sat well against the reference; hats read slightly ahead.",
            },
          ]}
        />
      }
    />
  );
}
