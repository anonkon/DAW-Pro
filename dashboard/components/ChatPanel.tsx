import type { AnalysisResult } from "@/lib/types";

const SEVERITY_COLOR: Record<string, string> = {
  info: "border-zinc-700",
  warning: "border-amber-600",
  critical: "border-red-600",
};

export function ChatPanel({ result }: { result: AnalysisResult }) {
  return (
    <div className="space-y-3">
      <div className="rounded-lg rounded-tl-none border border-zinc-700 bg-zinc-800 px-4 py-3 text-sm">
        {result.summary}
        {result.mix_score !== null && (
          <div className="mt-2 text-xs text-zinc-400">Mix score: {result.mix_score}/100</div>
        )}
      </div>
      {result.issues.map((issue, i) => (
        <div
          key={i}
          className={`rounded-lg rounded-tl-none border bg-zinc-900 px-4 py-3 text-sm ${SEVERITY_COLOR[issue.severity]}`}
        >
          <div className="font-medium">{issue.title}</div>
          <div className="mt-1 text-zinc-400">{issue.description}</div>
        </div>
      ))}
      {result.issues.length === 0 && (
        <p className="text-sm text-zinc-500">No specific issues flagged.</p>
      )}
    </div>
  );
}
