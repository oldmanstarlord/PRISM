import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { TerminalPanel } from "./Terminal";
import { fetchJson } from "./api";
import type { NewsFeed } from "./NewsIntelligence";
export default function NetworkEvidence({ symbol }: { symbol?: string }) {
  const [feed, setFeed] = useState<NewsFeed | null>(null);
  const [error, setError] = useState(false);
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    const controller = new AbortController();
    const load = () => {
      setNow(Date.now());
      void fetchJson<NewsFeed>("/news", controller.signal)
        .then((value) => {
          if (!controller.signal.aborted) {
            setFeed(value);
            setError(false);
          }
        })
        .catch(() => {
          if (!controller.signal.aborted) setError(true);
        });
    };
    load();
    const timer = setInterval(load, 30000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, []);
  const articles = (feed?.articles ?? [])
    .filter((article) => {
      const date = article.published_at
        ? Date.parse(article.published_at)
        : NaN;
      return (
        date <= now &&
        date >= now - 7 * 86400000 &&
        (!symbol || Object.hasOwn(article.companies, symbol))
      );
    })
    .slice(0, 4);
  return (
    <TerminalPanel title="News" meta={`${symbol ?? "MARKET"} / 7D`}>
      {error && <div>ERR: NEWS FEED{feed ? " / CACHED DATA" : ""}</div>}
      {articles.map((article) => (
        <div className="news-row" key={article.url}>
          <div className="terminal-panel-meta">
            {article.publisher} /{" "}
            {new Date(article.published_at!).toLocaleDateString("en-IN")}
          </div>
          <a href={article.url} target="_blank" rel="noopener noreferrer">
            {article.title}
          </a>
        </div>
      ))}
      {!articles.length && !error && (
        <div>{!feed ? "LOADING..." : "NO DATA"}</div>
      )}
      <Link to="/news">NEWS &gt;</Link>
    </TerminalPanel>
  );
}
