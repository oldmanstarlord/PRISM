import type { ReactNode } from "react";
export interface AppShellProps {
  children: ReactNode;
  subtitle?: string;
  actions?: ReactNode;
}
export default function AppShell({
  children,
  actions,
  subtitle,
}: AppShellProps) {
  return (
    <div
      className="terminal-page"
      onClick={(event) => {
        const target = event.target;
        if (!(target instanceof Element)) return;
        const row = target.closest("tbody tr");
        if (!row) return;
        row
          .closest("tbody")
          ?.querySelectorAll("[data-terminal-selected]")
          .forEach((item) => item.removeAttribute("data-terminal-selected"));
        row.setAttribute("data-terminal-selected", "true");
      }}
    >
      <header className="terminal-page-heading">
        <span>{subtitle ?? "Market research"}</span>
        {actions}
      </header>
      {children}
      <footer>RESEARCH ONLY / NO INVESTMENT ADVICE</footer>
    </div>
  );
}
