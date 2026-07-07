import { createClient } from "@/lib/supabase/server";
import type { Persona, Session } from "@/lib/types";
import { DashboardView } from "@/components/DashboardView";

export default async function DashboardPage() {
  const supabase = await createClient();

  const [{ data: personas }, { data: sessions }] = await Promise.all([
    supabase.from("personas").select("*").order("created_at", { ascending: false }),
    supabase.from("sessions").select("*").order("created_at", { ascending: false }),
  ]);

  return (
    <DashboardView
      initialPersonas={(personas as Persona[]) ?? []}
      initialSessions={(sessions as Session[]) ?? []}
    />
  );
}
