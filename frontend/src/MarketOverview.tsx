import { Link } from "react-router-dom";

import type { RankingsResponse } from "./types";

import { TerminalPanel, SummaryStrip } from "./Terminal";

export default function MarketOverview({
  data,
  horizon,
}: {
  data: RankingsResponse | null;
  horizon: number;
}) {
  const rows = data?.results ?? [];

  const ranked = [...rows]
    .sort((a, b) => Math.abs(b.divergence_value) - Math.abs(a.divergence_value))
    .slice(0, 12);

  const above = rows.filter((row) => row.divergence_value >= 0).length;

  return (
    <TerminalPanel
      title="Peer divergence"
      meta={data?.run.signal_date ?? "NO DATA"}
    >
      <SummaryStrip
        items={[
          { label: "COMPANIES", value: data ? rows.length : "—" },
          { label: "ABOVE", value: data ? above : "—" },
          { label: "BELOW", value: data ? rows.length - above : "—" },
        ]}
      />

      <table aria-label="Largest peer differences">
        <thead>
          <tr>
            <th>SYMBOL</th>
            <th>INDUSTRY</th>
            <th className="numeric">DIVERGENCE</th>
            <th>SIGNAL</th>
          </tr>
        </thead>
        <tbody>
          {ranked.map((row) => (
            <tr key={row.symbol}>
              <td>
                <Link
                  className="ticker"
                  to={`/companies/${encodeURIComponent(row.symbol)}?horizon=${horizon}`}
                >
                  {row.symbol}
                </Link>
              </td>
              <td>{row.industry}</td>
              <td
                className={`numeric ${row.divergence_value >= 0 ? "up" : "down"}`}
              >
                {row.divergence_value >= 0 ? "+" : ""}
                {row.divergence_value.toFixed(2)}
              </td>
              <td>{row.interpretation}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <div>NO DATA</div>}
    </TerminalPanel>
  );
}
