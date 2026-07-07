"use client";

import { useEffect, useRef } from "react";
import type WaveSurfer from "wavesurfer.js";

export function Waveform({ audioUrl }: { audioUrl: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;

    import("wavesurfer.js").then(({ default: WaveSurfer }) => {
      if (cancelled || !containerRef.current) return;
      wavesurferRef.current = WaveSurfer.create({
        container: containerRef.current,
        waveColor: "#52525b",
        progressColor: "#10b981",
        height: 96,
        url: audioUrl,
      });
    });

    return () => {
      cancelled = true;
      wavesurferRef.current?.destroy();
      wavesurferRef.current = null;
    };
  }, [audioUrl]);

  return <div ref={containerRef} className="w-full rounded border border-zinc-800 bg-zinc-950 p-2" />;
}
