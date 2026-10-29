import { useSyncExternalStore } from "react";
import { TerminalPanel, SummaryStrip } from "./Terminal";

function subscribe(callback: () => void) {
  window.addEventListener("storage", callback);
  window.addEventListener("prism:holdings", callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener("prism:holdings", callback);
  };
}
function snapshot() {
  try {
    return localStorage.getItem("prism_portfolio_holdings") ?? "[]";
  } catch {
    return "[]";
  }
}
export default function NetworkExposure({ symbol }: { symbol?: string }) {
  const raw = useSyncExternalStore(subscribe, snapshot, () => "[]");
  let holdings: {
    symbol: string;
    sector: string;
    quantity: number;
    buyPrice: number;
  }[] = [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (Array.isArray(parsed))
      holdings = parsed
        .filter(
          (h) =>
            typeof h.symbol === "string" &&
            Number.isFinite(h.quantity) &&
            h.quantity > 0 &&
            Number.isFinite(h.buyPrice) &&
            h.buyPrice > 0,
        )
        .map((h) => ({
          ...h,
          sector: typeof h.sector === "string" ? h.sector : "Unclassified",
        }));
  } catch {
    /* Invalid saved data is not presented as exposure. */
  }
  const total = holdings.reduce((sum, h) => sum + h.quantity * h.buyPrice, 0);
  const held = holdings
    .filter((h) => h.symbol === symbol)
    .reduce((sum, h) => sum + h.quantity * h.buyPrice, 0);
  return (
    <TerminalPanel title="Portfolio exposure" meta="COST BASIS / INR">
      <SummaryStrip
        items={[
          { label: "TOTAL", value: total.toFixed(2) },
          {
            label: symbol ?? "HOLDINGS",
            value: symbol
              ? `${((held / (total || 1)) * 100).toFixed(1)}%`
              : holdings.length,
          },
        ]}
      />
      <table>
        <thead>
          <tr>
            <th>SYMBOL</th>
            <th className="numeric">COST</th>
            <th className="numeric">WEIGHT</th>
          </tr>
        </thead>
        <tbody>
          {holdings.map((h, i) => (
            <tr
              key={`${h.symbol}-${i}`}
              data-terminal-selected={h.symbol === symbol || undefined}
            >
              <td className="ticker">{h.symbol}</td>
              <td className="numeric">
                {(h.quantity * h.buyPrice).toFixed(2)}
              </td>
              <td className="numeric">
                {(((h.quantity * h.buyPrice) / (total || 1)) * 100).toFixed(1)}%
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!holdings.length && <div>NO HOLDINGS</div>}
    </TerminalPanel>
  );
}
