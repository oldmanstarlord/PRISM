import type { ReactNode } from "react";
export function TerminalPanel({
  title,
  meta,
  controls,
  children,
  className = "",
}: {
  title: string;
  meta?: ReactNode;
  controls?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`terminal-panel ${className}`}>
      <header className="terminal-panel-heading">
        <span>
          {title}
          <span className="terminal-panel-meta">{meta}</span>
        </span>
        <span className="terminal-panel-controls">{controls}</span>
      </header>
      <div className="terminal-panel-body">{children}</div>
    </section>
  );
}
export function SummaryStrip({
  items,
}: {
  items: { label: string; value: ReactNode; direction?: "up" | "down" }[];
}) {
  return (
    <div className="summary-strip">
      {items.map((item) => (
        <span key={item.label}>
          <label>{item.label}</label>
          <span className={item.direction ?? ""}>{item.value}</span>
        </span>
      ))}
    </div>
  );
}
