"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import type { FeedbackTone, Persona, Session, SkillLevel } from "@/lib/types";

export function DashboardView({
  initialPersonas,
  initialSessions,
}: {
  initialPersonas: Persona[];
  initialSessions: Session[];
}) {
  const router = useRouter();
  const supabase = createClient();

  const [personas, setPersonas] = useState(initialPersonas);
  const [sessions, setSessions] = useState(initialSessions);

  const [personaName, setPersonaName] = useState("");
  const [skillLevel, setSkillLevel] = useState<SkillLevel>("beginner");
  const [feedbackTone, setFeedbackTone] = useState<FeedbackTone>("guided");
  const [genres, setGenres] = useState("");

  const [projectName, setProjectName] = useState("");
  const [selectedPersonaId, setSelectedPersonaId] = useState<string>(
    initialPersonas[0]?.id ?? ""
  );

  const [error, setError] = useState<string | null>(null);

  const createPersona = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return;

    const { data, error: insertError } = await supabase
      .from("personas")
      .insert({
        account_id: user.id,
        name: personaName,
        skill_level: skillLevel,
        feedback_tone: feedbackTone,
        preferred_genres: genres
          .split(",")
          .map((g) => g.trim())
          .filter(Boolean),
      })
      .select()
      .single();

    if (insertError) {
      setError(insertError.message);
      return;
    }

    setPersonas([data as Persona, ...personas]);
    setSelectedPersonaId((data as Persona).id);
    setPersonaName("");
    setGenres("");
  };

  const createSession = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!selectedPersonaId) {
      setError("Create a persona first.");
      return;
    }
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return;

    const { data, error: insertError } = await supabase
      .from("sessions")
      .insert({
        account_id: user.id,
        persona_id: selectedPersonaId,
        project_name: projectName,
      })
      .select()
      .single();

    if (insertError) {
      setError(insertError.message);
      return;
    }

    router.push(`/session/${(data as Session).id}`);
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  };

  return (
    <main className="mx-auto max-w-3xl px-4 py-10 space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">
          daw<span className="text-zinc-500">pro</span>
        </h1>
        <button onClick={signOut} className="text-sm text-zinc-500 hover:text-zinc-300">
          Sign out
        </button>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      <section className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <h2 className="text-sm font-medium text-zinc-300">Personas</h2>
        <ul className="space-y-1 text-sm text-zinc-400">
          {personas.map((p) => (
            <li key={p.id}>
              {p.name} — {p.skill_level}, {p.feedback_tone}
              {p.preferred_genres.length > 0 && ` (${p.preferred_genres.join(", ")})`}
            </li>
          ))}
          {personas.length === 0 && <li>No personas yet — create one below.</li>}
        </ul>

        <form onSubmit={createPersona} className="grid grid-cols-2 gap-2 pt-2">
          <input
            placeholder="Persona name"
            value={personaName}
            onChange={(e) => setPersonaName(e.target.value)}
            required
            className="col-span-2 rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm outline-none focus:border-zinc-500"
          />
          <select
            value={skillLevel}
            onChange={(e) => setSkillLevel(e.target.value as SkillLevel)}
            className="rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm"
          >
            <option value="beginner">beginner</option>
            <option value="intermediate">intermediate</option>
            <option value="advanced">advanced</option>
          </select>
          <select
            value={feedbackTone}
            onChange={(e) => setFeedbackTone(e.target.value as FeedbackTone)}
            className="rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm"
          >
            <option value="guided">guided</option>
            <option value="direct">direct</option>
            <option value="technical">technical</option>
          </select>
          <input
            placeholder="Preferred genres (comma separated)"
            value={genres}
            onChange={(e) => setGenres(e.target.value)}
            className="col-span-2 rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm outline-none focus:border-zinc-500"
          />
          <button
            type="submit"
            className="col-span-2 rounded bg-zinc-700 px-3 py-1.5 text-sm hover:bg-zinc-600"
          >
            Add persona
          </button>
        </form>
      </section>

      <section className="space-y-3 rounded-lg border border-zinc-800 bg-zinc-900 p-5">
        <h2 className="text-sm font-medium text-zinc-300">New session</h2>
        <form onSubmit={createSession} className="flex gap-2">
          <input
            placeholder="Project name"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            required
            className="flex-1 rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm outline-none focus:border-zinc-500"
          />
          <select
            value={selectedPersonaId}
            onChange={(e) => setSelectedPersonaId(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-sm"
          >
            {personas.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            type="submit"
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500"
          >
            Create
          </button>
        </form>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-zinc-300">Sessions</h2>
        <ul className="divide-y divide-zinc-800 rounded-lg border border-zinc-800 bg-zinc-900">
          {sessions.map((s) => (
            <li key={s.id}>
              <Link
                href={`/session/${s.id}`}
                className="block px-4 py-3 text-sm hover:bg-zinc-800"
              >
                {s.project_name}
              </Link>
            </li>
          ))}
          {sessions.length === 0 && (
            <li className="px-4 py-3 text-sm text-zinc-500">No sessions yet.</li>
          )}
        </ul>
      </section>
    </main>
  );
}
