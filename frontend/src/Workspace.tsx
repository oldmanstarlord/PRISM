import {
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type FormEvent,
} from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { fetchJson } from "./api";
import type { BenchmarkQuote } from "./types";
type Tab = { path: string; url: string; title: string };
const pages = [
  { path: "/", title: "Markets", command: "MKT" },
  { path: "/portfolio", title: "My portfolio", command: "PORT" },
  { path: "/mst", title: "Network", command: "NET" },
  { path: "/news", title: "News", command: "NEWS" },
];
function readTabs(): Tab[] {
  try {
    const saved: unknown = JSON.parse(
      sessionStorage.getItem("prism.workspace.tabs") ?? "[]",
    );
    const seen = new Set<string>();
    return Array.isArray(saved)
      ? saved.filter((t): t is Tab => {
          const valid =
            t &&
            typeof t.path === "string" &&
            typeof t.url === "string" &&
            typeof t.title === "string" &&
            !seen.has(t.path) &&
            (pages.some((p) => p.path === t.path) ||
              /^\/companies\/[^/?#]+$/.test(t.path)) &&
            t.url.split("?")[0] === t.path;
          if (valid) seen.add(t.path);
          return Boolean(valid);
        })
      : [];
  } catch {
    return [];
  }
}
export default function Workspace({
  renderPage,
}: {
  renderPage: (url: string) => ReactNode;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const [tabs, setTabs] = useState<Tab[]>(readTabs);
  const [collapsed, setCollapsed] = useState(false);
  const [dragged, setDragged] = useState<string | null>(null);
  const [over, setOver] = useState<string | null>(null);
  const [quote, setQuote] = useState<BenchmarkQuote | null>(null);
  const [connected, setConnected] = useState(false);
  const [observedUrl, setObservedUrl] = useState<string | null>(null);
  const [command, setCommand] = useState("");
  const [message, setMessage] = useState("MKT / PORT / NET / NEWS / SYMBOL");
  const [clock, setClock] = useState(() => new Date());
  const [flash, setFlash] = useState<"up" | "down" | null>(null);
  const previousPrice = useRef<number | null>(null);
  const commandInput = useRef<HTMLInputElement>(null);
  const active: Tab = {
    path: location.pathname,
    url: location.pathname + location.search,
    title:
      pages.find((p) => p.path === location.pathname)?.title ??
      location.pathname.split("/").pop() ??
      "Research",
  };
  const existing = tabs.find((t) => t.path === active.path);
  if (observedUrl !== active.url) {
    setObservedUrl(active.url);
    setTabs(
      existing
        ? tabs.map((t) => (t.path === active.path ? active : t))
        : [...tabs, active],
    );
  }
  useEffect(() => {
    try {
      sessionStorage.setItem("prism.workspace.tabs", JSON.stringify(tabs));
    } catch {
      /* Storage disabled. */
    }
  }, [tabs]);
  useEffect(() => {
    const timer = setInterval(() => setClock(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let flashTimer: ReturnType<typeof setTimeout>;
    const refresh = () => {
      void fetchJson<BenchmarkQuote>(
        "/market-data/benchmark",
        controller.signal,
      )
        .then((value) => {
          if (controller.signal.aborted) return;
          setQuote(value);
          setConnected(value.latest_price != null);
          if (
            previousPrice.current != null &&
            value.latest_price != null &&
            previousPrice.current !== value.latest_price
          ) {
            setFlash(
              value.latest_price > previousPrice.current ? "up" : "down",
            );
            clearTimeout(flashTimer);
            flashTimer = setTimeout(() => setFlash(null), 150);
          }
          previousPrice.current = value.latest_price;
        })
        .catch(() => {
          if (!controller.signal.aborted) setConnected(false);
        });
    };
    refresh();
    const timer = setInterval(refresh, 60_000);
    return () => {
      controller.abort();
      clearInterval(timer);
      clearTimeout(flashTimer);
    };
  }, []);
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "k") {
        event.preventDefault();
        commandInput.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  function move(path: string, target: string) {
    if (path === target) return;
    setTabs((current) => {
      const next = [...current];
      const from = next.findIndex((t) => t.path === path),
        to = next.findIndex((t) => t.path === target);
      if (from < 0 || to < 0) return current;
      next.splice(to, 0, next.splice(from, 1)[0]);
      return next;
    });
  }
  function close(path: string) {
    const index = tabs.findIndex((t) => t.path === path);
    const next = tabs.filter((t) => t.path !== path);
    if (path === active.path)
      navigate(next[Math.min(index, next.length - 1)]?.url ?? "/");
    setTabs(next);
  }
  function execute(event: FormEvent) {
    event.preventDefault();
    const value = command
      .trim()
      .toUpperCase()
      .replace(/\s*<GO>$/, "");
    const destination = pages.find((p) => p.command === value);
    if (destination) {
      navigate(
        tabs.find((t) => t.path === destination.path)?.url ?? destination.path,
      );
      setMessage(`${value} OK`);
      setCommand("");
    } else if (value === "HELP") {
      setMessage("MKT / PORT / NET / NEWS / SYMBOL / CTRL+K");
    } else if (/^[A-Z0-9][A-Z0-9.&-]{0,19}$/.test(value)) {
      navigate(`/companies/${encodeURIComponent(value)}`);
      setMessage(`${value} RESEARCH`);
      setCommand("");
    } else {
      setMessage("ERR: ENTER COMMAND OR SYMBOL");
    }
  }
  return (
    <div className="terminal-frame">
      <a
        className="skip-link"
        href={`#workspace-panel-${tabs.findIndex((t) => t.path === active.path)}`}
      >
        Skip to content
      </a>
      <form className="command-bar" onSubmit={execute}>
        <Link className="command-prompt" to="/" aria-label="PRISM">
          PRISM&gt;
        </Link>
        <input
          ref={commandInput}
          aria-label="Command"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          autoComplete="off"
          spellCheck={false}
          placeholder="MKT | PORT | NET | NEWS | SYMBOL"
        />
        <button className="terminal-button go-key" type="submit">
          GO
        </button>
        <button
          className="terminal-button"
          type="button"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? "[+]" : "[-]"}
        </button>
      </form>
      <div className="market-strip">
        <span>
          <label>NIFTY 50</label>
          <span className={flash ? `cell-flash-${flash}` : ""}>
            {quote?.latest_price?.toLocaleString("en-IN", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            }) ?? "NO DATA"}
          </span>
        </span>
        <span
          className={
            quote?.change_percent != null && quote.change_percent < 0
              ? "down"
              : "up"
          }
        >
          {quote?.change_percent == null
            ? "—"
            : `${quote.change_percent >= 0 ? "+" : ""}${quote.change_percent.toFixed(2)}%`}
        </span>
        <span>
          <label>AS OF</label>
          {quote?.as_of ?? "—"}
        </span>
        <span className="command-result" role="status">
          {message}
        </span>
      </div>
      <div className={`workspace-body ${collapsed ? "collapsed" : ""}`}>
        {!collapsed && (
          <nav className="terminal-nav" aria-label="Main navigation">
            {pages.map((p) => (
              <Link
                key={p.path}
                to={tabs.find((t) => t.path === p.path)?.url ?? p.path}
                aria-current={active.path === p.path ? "page" : undefined}
              >
                {p.title}
              </Link>
            ))}
          </nav>
        )}
        <div className="workspace-main">
          <div
            className="workspace-tabs"
            role="tablist"
            aria-label="Open research pages"
          >
            {tabs.map((tab, i) => (
              <div
                key={tab.path}
                className={`workspace-tab ${active.path === tab.path ? "active" : ""} ${over === tab.path && dragged !== tab.path ? "drop-target" : ""}`}
                draggable
                onDragStart={(e) => {
                  setDragged(tab.path);
                  e.dataTransfer.setData("text/plain", tab.path);
                  e.dataTransfer.effectAllowed = "move";
                }}
                onDragOver={(e) => {
                  e.preventDefault();
                  setOver(tab.path);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  if (dragged) move(dragged, tab.path);
                  setDragged(null);
                  setOver(null);
                }}
                onDragEnd={() => {
                  setDragged(null);
                  setOver(null);
                }}
              >
                <button
                  role="tab"
                  id={`workspace-tab-${i}`}
                  aria-controls={`workspace-panel-${i}`}
                  aria-selected={active.path === tab.path}
                  onClick={() => navigate(tab.url)}
                  onKeyDown={(e) => {
                    if (["ArrowLeft", "ArrowRight"].includes(e.key)) {
                      e.preventDefault();
                      const next =
                        (i + (e.key === "ArrowLeft" ? -1 : 1) + tabs.length) %
                        tabs.length;
                      if (e.altKey) move(tab.path, tabs[next].path);
                      else {
                        navigate(tabs[next].url);
                        document
                          .getElementById(`workspace-tab-${next}`)
                          ?.focus();
                      }
                    }
                  }}
                  title="Drag to reorder; Alt + arrow keys"
                >
                  {tab.title}
                </button>
                <button
                  aria-label={`Close ${tab.title}`}
                  onClick={() => close(tab.path)}
                  disabled={tabs.length === 1}
                >
                  [x]
                </button>
              </div>
            ))}
          </div>
          {tabs.map((tab, i) => (
            <main
              key={tab.path}
              className="workspace-panel"
              role="tabpanel"
              tabIndex={-1}
              id={`workspace-panel-${i}`}
              aria-labelledby={`workspace-tab-${i}`}
              hidden={tab.path !== active.path}
            >
              {renderPage(tab.url)}
            </main>
          ))}
        </div>
      </div>
      <footer className="status-bar">
        <span>
          {clock.toLocaleString("en-IN", {
            timeZone: "Asia/Kolkata",
            hour12: false,
          })}{" "}
          IST
        </span>
        <span className={`connection-square ${connected ? "connected" : ""}`} />
        <span>{connected ? "BENCHMARK CONNECTED" : "BENCHMARK OFFLINE"}</span>
        <span>
          {quote && !connected
            ? "LAST RECEIVED QUOTE"
            : "SOURCE: MARKET DATA API"}
        </span>
        <span>{tabs.length} OPEN</span>
      </footer>
    </div>
  );
}
