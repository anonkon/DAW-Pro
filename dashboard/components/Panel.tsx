import type { ReactNode } from "react";

export function Panel({
  title,
  aside,
  children,
  className = "",
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-line bg-surface-panel p-5 ${className}`}>
      <header className="mb-4 flex items-baseline justify-between gap-3">
        <h2 className="label-caps">{title}</h2>
        {aside}
      </header>
      {children}
    </section>
  );
}
