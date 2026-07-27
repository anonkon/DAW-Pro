import Link from "next/link";
import type { Session } from "@/lib/types";

export type HistoryEntry = {
  job_id: string;
  created_at: string;
  summary: string | null;
};

/** The mockup's left rail, built only from things that exist.
 *
 * Its TRACKS / CLIPS / LIBRARY / PLUGINS items are DAW chrome - DAWpro sits
 * alongside Ableton rather than replacing it, so there are no tracks or clips
 * here to browse and those entries would navigate nowhere. Sessions, the
 * reference track and analysis history are real rows, so those are what the
 * rail carries.
 */
export function SideNav({
  sessions,
  currentSessionId,
  history = [],
  tempoBpm,
}: {
  sessions: Session[];
  currentSessionId?: string;
  history?: HistoryEntry[];
  tempoBpm?: number | null;
}) {
  const current = sessions.find((s) => s.id === currentSessionId);

  return (
    <nav className="flex h-full flex-col gap-6 border-r border-line bg-surface-panel p-4">
      <Link href="/dashboard" className="px-2 font-mono text-lg font-bold tracking-tight">
        daw<span style={{ color: "var(--accent)" }}>pro</span>
      </Link>

      {current && (
        <div className="flex items-center gap-3 rounded border border-line bg-surface-raised p-3">
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border"
            style={{ borderColor: "var(--viz-project)", color: "var(--viz-project)" }}
            aria-hidden
          >
            ●
          </span>
          <div className="min-w-0">
            <p className="truncate text-small font-medium text-ink-primary">
              {current.project_name}
            </p>
            <p className="text-label text-ink-muted">
              {tempoBpm ? `${Math.round(tempoBpm)} BPM` : "Tempo unknown"}
              {current.reference_track_s3_key ? " · reference set" : ""}
            </p>
          </div>
        </div>
      )}

      <Link
        href="/dashboard"
        className="rounded border border-line px-3 py-2 text-center text-small font-medium text-ink-primary transition-colors hover:bg-surface-hover"
      >
        + New session
      </Link>

      <div>
        <p className="label-caps px-2 pb-2">Sessions</p>
        <ul className="space-y-0.5">
          {sessions.slice(0, 8).map((s) => {
            const active = s.id === currentSessionId;
            return (
              <li key={s.id}>
                <Link
                  href={`/session/${s.id}`}
                  aria-current={active ? "page" : undefined}
                  className="flex items-center gap-2 rounded px-2 py-1.5 text-small transition-colors hover:bg-surface-hover"
                  style={
                    active
                      ? { background: "var(--surface-raised)", color: "var(--accent)" }
                      : { color: "var(--text-secondary)" }
                  }
                >
                  {/* Active state carries a visible marker, not colour alone. */}
                  <span
                    className="h-3.5 w-0.5 shrink-0 rounded-full"
                    style={{ background: active ? "var(--accent)" : "transparent" }}
                    aria-hidden
                  />
                  <span className="truncate">{s.project_name}</span>
                </Link>
              </li>
            );
          })}
          {sessions.length === 0 && (
            <li className="px-2 text-small text-ink-muted">No sessions yet.</li>
          )}
        </ul>
      </div>

      {currentSessionId && (
        <div className="min-h-0 flex-1">
          <p className="label-caps px-2 pb-2">History</p>
          {history.length === 0 ? (
            <p className="px-2 text-small text-ink-muted">No previous analyses.</p>
          ) : (
            <ul className="space-y-2 overflow-y-auto">
              {history.map((h) => (
                <li key={h.job_id} className="rounded px-2 py-1.5 hover:bg-surface-hover">
                  <p className="font-mono text-label text-ink-muted">
                    {new Date(h.created_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                  {h.summary && (
                    <p className="line-clamp-2 text-small text-ink-secondary">{h.summary}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </nav>
  );
}
