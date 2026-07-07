"use client";

import { useEffect, useState } from "react";
import { fetchJobStatus } from "@/lib/api";
import type { JobStatus } from "@/lib/types";

const POLL_INTERVAL_MS = 2000;

export function usePollJob(jobId: string | null) {
  const [status, setStatus] = useState<JobStatus | null>(null);

  useEffect(() => {
    if (!jobId) {
      setStatus(null);
      return;
    }

    let cancelled = false;

    const tick = async () => {
      try {
        const data = await fetchJobStatus(jobId);
        if (!cancelled) setStatus(data);
        if (!cancelled && (data.status === "done" || data.status === "failed")) {
          clearInterval(interval);
        }
      } catch {
        // transient network error - next tick retries, no need to surface every miss
      }
    };

    tick();
    const interval = setInterval(tick, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId]);

  return status;
}
