import { TerminalPanel, SummaryStrip } from "./Terminal";
import { resolveTerminalStyles } from "./terminalTokens";
import { ReviewDetails } from "./GuidedReview";
import { useEffect, useRef, useState } from "react";
import { Autocomplete, TextField } from "@mui/material";
import cytoscape, { type Core } from "cytoscape";
import { Link } from "react-router-dom";

import NetworkExposure from "./NetworkExposure";
import NetworkEvidence from "./NetworkEvidence";
import AppShell from "./AppShell";
import { fetchJson } from "./api";
import { CorrelationMstExplainer } from "./PrismExplainer";
import { getDecisionsCountMap, getNotesCountMap } from "./journalStorage";
import { industryColors, mstElements } from "./mstLayout";
import type { MstResponse } from "./types";

export default function MstPage() {
  const container = useRef<HTMLDivElement | null>(null);
  const graph = useRef<Core | null>(null);
  const [data, setData] = useState<MstResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [selected, setSelected] = useState<{
    title: string;
    detail: string;
    symbol?: string;
    isNode?: boolean;
  } | null>(null);
  const [notesCountMap, setNotesCountMap] = useState<Record<string, number>>(
    {},
  );
  const [decisionsCountMap, setDecisionsCountMap] = useState<
    Record<string, number>
  >({});

  useEffect(() => {
    void getNotesCountMap()
      .then(setNotesCountMap)
      .catch(() => {});
    void getDecisionsCountMap()
      .then(setDecisionsCountMap)
      .catch(() => {});
  }, []);

  function resetGraph() {
    if (!graph.current) return;
    graph.current.elements().removeClass("faded focused");
    graph.current.elements().unselect();
    graph.current.fit(undefined, 55);
    setSelected(null);
  }

  function zoomGraph(factor: number) {
    const current = graph.current;
    if (!current) return;
    current.zoom({
      level: Math.max(
        current.minZoom(),
        Math.min(current.maxZoom(), current.zoom() * factor),
      ),
      renderedPosition: { x: current.width() / 2, y: current.height() / 2 },
    });
  }

  function focusStock(id: string) {
    const current = graph.current;
    if (!current) return;
    const node = current.getElementById(id);
    node.emit("tap");
    current.fit(node.closedNeighborhood(), 90);
    current.zoom(Math.min(1.6, current.zoom()));
    current.center(node.closedNeighborhood());
  }

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<MstResponse>("/mst/latest", controller.signal)
      .then(setData)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError")
          return;
        setError(
          reason instanceof Error ? reason.message : "Unable to load MST",
        );
      });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => {
    if (!data || !container.current || !data.nodes.length) return;
    const instance = cytoscape({
      container: container.current,
      elements: mstElements(data),
      layout: {
        name: "cose",
        animate: false,
        randomize: false,
        nodeRepulsion: () => 18000,
        idealEdgeLength: () => 120,
        nodeOverlap: 30,
        componentSpacing: 60,
        gravity: 0.1,
        padding: 24,
      },
      minZoom: 0.04,
      maxZoom: 3,

      boxSelectionEnabled: false,
      style: resolveTerminalStyles([
        {
          selector: "node",
          style: {
            shape: "rectangle",
            label: "",
            "background-color": "data(color)",
            width: "mapData(degree, 0, 12, 14, 36)",
            height: "mapData(degree, 0, 12, 14, 36)",
            "border-width": 1,
            "border-color": "var(--bg)",
            color: "var(--white)",
            "font-family": "var(--font-data)",
            "font-size": "var(--text-label)",
            "min-zoomed-font-size": 10,
            "text-valign": "bottom",
            "text-margin-y": 8,
            "text-background-color": "var(--bg)",
            "text-background-opacity": 1,
            "text-background-padding": "var(--space-1)",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "var(--cyan)",
            opacity: 1,
            "curve-style": "straight",
          },
        },
        {
          selector: "node[degree >= 4]",
          style: {
            label: "data(symbol)",
            "font-size": "var(--text-label)",
            "font-weight": 600,
          },
        },
        {
          selector: "node.focused",
          style: { label: "data(symbol)", "font-size": "var(--text-label)" },
        },
        {
          selector: "edge.focused",
          style: { "line-color": "var(--amber)", width: 1, opacity: 1 },
        },
        {
          selector: "node:selected",
          style: {
            "background-color": "var(--amber)",
            "border-color": "var(--yellow)",
            "border-width": 1,
          },
        },
        {
          selector: "node.faded",
          style: { "background-color": "var(--gray)", color: "var(--gray)" },
        },
        { selector: "edge.faded", style: { "line-color": "var(--line)" } },
      ]),
    });
    graph.current = instance;
    const updateZoom = () => {
      setZoom(instance.zoom());
      instance.nodes().style("font-size", 11 / instance.zoom());
    };
    updateZoom();
    instance.on("zoom", updateZoom);
    instance.on("tap", "node", (event) => {
      const node = event.target;
      const value = node.data();
      instance.elements().unselect().removeClass("focused").addClass("faded");
      node.closedNeighborhood().removeClass("faded").addClass("focused");
      node.select();
      setSelected({
        title: value.symbol,
        detail: `${value.industry} · ${value.degree} MST connections`,
        symbol: value.symbol,
        isNode: true,
      });
    });
    instance.on("tap", "edge", (event) => {
      const edge = event.target;
      const value = edge.data();
      instance.elements().unselect().removeClass("focused").addClass("faded");
      edge.connectedNodes().add(edge).removeClass("faded").addClass("focused");
      edge.select();
      setSelected({
        title: `${value.symbol_a} / ${value.symbol_b}`,
        detail: `Correlation ${Number(value.correlation).toFixed(3)} · ${value.paired_observations} paired returns`,
        isNode: false,
      });
    });
    instance.on("tap", (event) => {
      if (event.target === instance) {
        instance.elements().removeClass("faded focused").unselect();
        setSelected(null);
      }
    });
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      instance.destroy();
      graph.current = null;
    };
  }, [data]);
  const colors = industryColors(data?.nodes.map((node) => node.industry) ?? []);
  const sectors = Object.entries(colors)
    .map(([name, color]) => ({
      name,
      color,
      count: data?.nodes.filter((node) => node.industry === name).length ?? 0,
    }))
    .sort((a, b) => b.count - a.count);
  const connections = (data?.edges ?? [])
    .filter(
      (edge) =>
        !selected?.symbol ||
        edge.symbol_a === selected.symbol ||
        edge.symbol_b === selected.symbol,
    )
    .sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation));
  const currentNode = data?.nodes.find(
    (node) => node.symbol === selected?.symbol,
  );
  const hubs = (data?.nodes ?? [])
    .map((node) => ({
      ...node,
      degree:
        data?.edges.filter(
          (edge) => edge.source === node.id || edge.target === node.id,
        ).length ?? 0,
    }))
    .sort((a, b) => b.degree - a.degree)
    .slice(0, 8);
  return (
    <AppShell subtitle="Network">
      <SummaryStrip
        items={[
          { label: "UNIVERSE", value: data?.nodes.length ?? "NO DATA" },
          { label: "EDGES", value: data?.edges.length ?? "—" },
          {
            label: "WINDOW",
            value: data
              ? `${data.run.window_start} / ${data.run.window_end}`
              : "—",
          },
          {
            label: "TOPOLOGY",
            value: data
              ? data.run.is_connected
                ? "CONNECTED"
                : "DISCONNECTED"
              : "NO DATA",
          },
          { label: "EXCLUDED", value: data?.run.exclusions.length ?? "—" },
        ]}
      />
      <div className="terminal-grid">
        <div className="panel-column">
          <TerminalPanel
            title="Market network"
            meta="MST / historical correlation"
            controls={
              <>
                <button
                  className="terminal-button"
                  aria-label="Zoom out"
                  onClick={() => zoomGraph(1 / 1.3)}
                >
                  [-]
                </button>
                <span>{Math.round(zoom * 100)}%</span>
                <button
                  className="terminal-button"
                  aria-label="Zoom in"
                  onClick={() => zoomGraph(1.3)}
                >
                  [+]
                </button>
                <button className="terminal-button" onClick={resetGraph}>
                  FIT
                </button>
              </>
            }
            className="network-panel"
          >
            <div className="network-toolbar">
              <Autocomplete
                options={[...(data?.nodes ?? [])].sort((a, b) =>
                  a.symbol.localeCompare(b.symbol),
                )}
                getOptionLabel={(node) => `${node.symbol} / ${node.industry}`}
                value={currentNode ?? null}
                onChange={(_, node) =>
                  node ? focusStock(node.id) : resetGraph()
                }
                renderInput={(params) => (
                  <TextField {...params} label="Symbol" />
                )}
                className="network-search"
              />
              <span className="terminal-panel-meta">
                SIZE: DEGREE / COLOUR: INDUSTRY
              </span>
            </div>
            <div className="network-canvas-wrap">
              <div
                ref={container}
                aria-label="correlation minimum spanning tree"
                className="network-canvas"
              />
              {(!data || !data.nodes.length) && (
                <div className="network-empty">
                  <span>
                    {error
                      ? "ERR: NETWORK UNAVAILABLE"
                      : data
                        ? "NO DATA"
                        : "LOADING..."}
                  </span>
                  {error && (
                    <button
                      className="terminal-button"
                      onClick={() => {
                        setError(null);
                        setRevision((value) => value + 1);
                      }}
                    >
                      RETRY
                    </button>
                  )}
                </div>
              )}
            </div>
          </TerminalPanel>
          <TerminalPanel
            title="Retained relationships"
            meta={selected?.symbol ?? "ALL"}
          >
            <table>
              <thead>
                <tr>
                  <th>SYMBOL A</th>
                  <th>SYMBOL B</th>
                  <th className="numeric">CORRELATION</th>
                  <th className="numeric">OBS.</th>
                  <th className="numeric">DISTANCE</th>
                </tr>
              </thead>
              <tbody>
                {connections.slice(0, 12).map((edge) => (
                  <tr key={`${edge.source}-${edge.target}`}>
                    <td>
                      <button
                        className="table-link"
                        onClick={() => focusStock(edge.source)}
                      >
                        {edge.symbol_a}
                      </button>
                    </td>
                    <td>
                      <button
                        className="table-link"
                        onClick={() => focusStock(edge.target)}
                      >
                        {edge.symbol_b}
                      </button>
                    </td>
                    <td
                      className={`numeric ${edge.correlation >= 0 ? "up" : "down"}`}
                    >
                      {edge.correlation >= 0 ? "+" : ""}
                      {edge.correlation.toFixed(3)}
                    </td>
                    <td className="numeric">{edge.paired_observations}</td>
                    <td className="numeric">{edge.distance.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!connections.length && <div>NO DATA</div>}
          </TerminalPanel>
        </div>
        <div className="panel-column">
          <TerminalPanel title="Security" meta={selected?.symbol ?? "NONE"}>
            <div className="ticker">{selected?.title ?? "SELECT SYMBOL"}</div>
            <div>{selected?.detail ?? "NO SELECTION"}</div>
            {selected?.symbol && (
              <>
                <SummaryStrip
                  items={[
                    {
                      label: "NOTES",
                      value: notesCountMap[selected.symbol] ?? 0,
                    },
                    {
                      label: "DECISIONS",
                      value: decisionsCountMap[selected.symbol] ?? 0,
                    },
                    {
                      label: "OBS.",
                      value: currentNode?.observations_used ?? "—",
                    },
                  ]}
                />
                <Link to={`/companies/${encodeURIComponent(selected.symbol)}`}>
                  RESEARCH &gt;
                </Link>
              </>
            )}
          </TerminalPanel>
          <TerminalPanel title="Industries" meta="COMPANY COUNT">
            <table>
              <thead>
                <tr>
                  <th>INDUSTRY</th>
                  <th className="numeric">N</th>
                </tr>
              </thead>
              <tbody>
                {sectors.map((sector) => (
                  <tr
                    key={sector.name}
                    data-terminal-selected={
                      currentNode?.industry === sector.name || undefined
                    }
                  >
                    <td>{sector.name}</td>
                    <td className="numeric">{sector.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!sectors.length && <div>NO DATA</div>}
          </TerminalPanel>
          <TerminalPanel title="Junctions" meta="RETAINED DEGREE">
            <table>
              <thead>
                <tr>
                  <th>SYMBOL</th>
                  <th className="numeric">EDGES</th>
                </tr>
              </thead>
              <tbody>
                {hubs.map((node) => (
                  <tr key={node.id}>
                    <td>
                      <button
                        className="table-link"
                        onClick={() => focusStock(node.id)}
                      >
                        {node.symbol}
                      </button>
                    </td>
                    <td className="numeric">{node.degree}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TerminalPanel>
          <NetworkExposure symbol={selected?.symbol} />
          <NetworkEvidence symbol={selected?.symbol} />
        </div>
      </div>
      <ReviewDetails title="Methodology">
        <div>{data ? `COMPUTED ${data.run.computed_at}` : "NO DATA"}</div>
        <CorrelationMstExplainer />
      </ReviewDetails>
    </AppShell>
  );
}
