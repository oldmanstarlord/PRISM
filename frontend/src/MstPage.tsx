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
import {
  industryColors,
  layoutMst,
  mstLayout,
  type MstLayoutResult,
} from "./mstLayout";
import type { MstResponse } from "./types";

interface SecurityInfo {
  symbol: string;
  company_name: string;
}

function clearGraphFocus(instance: Core) {
  instance.elements().removeClass("faded focused").unselect();
}

function focusNeighborhood(instance: Core, nodeId: string) {
  const node = instance.getElementById(nodeId);
  if (!node.length) return;
  instance.elements().removeClass("focused").addClass("faded");
  node.closedNeighborhood().removeClass("faded").addClass("focused");
}

function edgePassesLimit(edge: cytoscape.EdgeSingular, limit: number) {
  return (
    Number(edge.data("sourceRank")) <= limit &&
    Number(edge.data("targetRank")) <= limit
  );
}

function applyGraphFilters(
  instance: Core,
  hiddenSectors: string[],
  topEdges: number,
) {
  const hidden = new Set(hiddenSectors);
  instance.nodes().forEach((node) => {
    node.toggleClass("sector-hidden", hidden.has(String(node.data("industry"))));
  });
  instance.edges().forEach((edge) => {
    edge.toggleClass("edge-filtered", !edgePassesLimit(edge, topEdges));
    edge.toggleClass(
      "sector-hidden",
      edge.connectedNodes().some((node) => hidden.has(String(node.data("industry")))),
    );
  });
}

export default function MstPage() {
  const container = useRef<HTMLDivElement | null>(null);
  const graph = useRef<Core | null>(null);
  const selectedNodeId = useRef<string | null>(null);
  const [data, setData] = useState<MstResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [topEdges, setTopEdges] = useState(5);
  const [hiddenSectors, setHiddenSectors] = useState<string[]>([]);
  const [layoutInfo, setLayoutInfo] = useState<MstLayoutResult | null>(null);
  const [companyNames, setCompanyNames] = useState<Record<string, string>>({});
  const [hovered, setHovered] = useState<{
    x: number;
    y: number;
    symbol: string;
    industry: string;
    degree: number;
  } | null>(null);
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
    const controller = new AbortController();
    void fetchJson<SecurityInfo[]>("/securities", controller.signal)
      .then((securities) =>
        setCompanyNames(
          Object.fromEntries(
            securities.map((security) => [security.symbol, security.company_name]),
          ),
        ),
      )
      .catch(() => {});
    return () => controller.abort();
  }, []);

  function fitGraph(instance: Core) {
    const visibleNodes = instance
      .nodes()
      .not(".sector-hidden")
      .nodes();
    if (!visibleNodes.length) return;
    instance.fit(visibleNodes, 40);
    let minimum = Number.POSITIVE_INFINITY;
    const positions = visibleNodes.map((node) => node.renderedPosition());
    for (let left = 0; left < positions.length; left += 1) {
      for (let right = left + 1; right < positions.length; right += 1) {
        minimum = Math.min(
          minimum,
          Math.hypot(
            positions[left].x - positions[right].x,
            positions[left].y - positions[right].y,
          ),
        );
      }
    }
    if (Number.isFinite(minimum) && minimum < 40) {
      instance.zoom(instance.zoom() * (40 / Math.max(1, minimum)));
      instance.center(visibleNodes);
    }
  }

  function resetGraph() {
    if (!graph.current) return;
    selectedNodeId.current = null;
    clearGraphFocus(graph.current);
    fitGraph(graph.current);
    setSelected(null);
    setHovered(null);
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
    const laidOut = layoutMst(data, {
      width: container.current.clientWidth,
      height: container.current.clientHeight,
    });
    setLayoutInfo(laidOut);
    console.info(
      `[PRISM network] label overlaps: ${laidOut.labelOverlapCount}; minimum node distance: ${laidOut.minimumNodeDistance.toFixed(1)}px; force ticks: ${laidOut.forceTicks}`,
    );
    const instance = cytoscape({
      container: container.current,
      elements: laidOut.elements,
      layout: mstLayout(),
      minZoom: 0.1,
      maxZoom: 3,
      boxSelectionEnabled: false,
      autoungrabify: false,
      style: resolveTerminalStyles([
        {
          selector: "node",
          style: {
            shape: "ellipse",
            label: "data(symbol)",
            "background-color": "data(color)",
            width: "mapData(radius, 6, 22, 12, 44)",
            height: "mapData(radius, 6, 22, 12, 44)",
            "border-width": 1,
            "border-color": "var(--bg)",
            color: "var(--white)",
            "font-family": "var(--font-data)",
            "font-size": 11,
            "font-weight": 600,
            "min-zoomed-font-size": 0,
            "text-halign": "data(labelHalign)",
            "text-valign": "data(labelValign)",
            "text-margin-x": "data(labelMarginX)",
            "text-margin-y": "data(labelMarginY)",
            "text-outline-color": "var(--bg)",
            "text-outline-width": 3,
            "text-outline-opacity": 1,
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(strength, 0, 1, 1.8, 3)",
            "line-color": "var(--white)",
            opacity: "data(edgeOpacity)",
            "curve-style": "straight",
          },
        },
        {
          selector: "node.focused",
          style: {
            opacity: 1,
          },
        },
        {
          selector: "edge.focused",
          style: { "line-color": "var(--amber)", width: 3.5, opacity: 1 },
        },
        {
          selector: "node:selected",
          style: { "border-color": "var(--amber)", "border-width": 2 },
        },
        {
          selector: "node.faded",
          style: { opacity: 0.08 },
        },
        {
          selector: "edge.faded",
          style: { opacity: 0.08 },
        },
        {
          selector: ".sector-hidden, edge.edge-filtered",
          style: { display: "none" },
        },
      ]) as cytoscape.StylesheetJson,
    });
    graph.current = instance;
    fitGraph(instance);
    const updateZoom = () => {
      setZoom(instance.zoom());
      instance.nodes().style("font-size", 11 / instance.zoom());
      instance.nodes().style("text-outline-width", 3 / instance.zoom());
    };
    updateZoom();
    instance.on("zoom", updateZoom);
    instance.on("mouseover", "node", (event) => {
      const node = event.target;
      const value = node.data();
      focusNeighborhood(instance, node.id());
      const position = node.renderedPosition();
      setHovered({
        x: position.x,
        y: position.y,
        symbol: String(value.symbol),
        industry: String(value.industry),
        degree: Number(value.degree),
      });
    });
    instance.on("mouseout", "node", () => {
      setHovered(null);
      if (selectedNodeId.current) {
        focusNeighborhood(instance, selectedNodeId.current);
      } else {
        clearGraphFocus(instance);
      }
    });
    instance.on("tap", "node", (event) => {
      const node = event.target;
      const value = node.data();
      selectedNodeId.current = node.id();
      focusNeighborhood(instance, node.id());
      instance.elements().unselect();
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
      selectedNodeId.current = null;
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
        selectedNodeId.current = null;
        clearGraphFocus(instance);
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
  useEffect(() => {
    if (!graph.current) return;
    applyGraphFilters(graph.current, hiddenSectors, topEdges);
    fitGraph(graph.current);
  }, [hiddenSectors, topEdges]);
  const colors = industryColors(data?.nodes.map((node) => node.industry) ?? []);
  const topology = layoutInfo?.topology ?? null;
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
                  RESET VIEW
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
              <label className="network-edge-limit">
                <span>TOP {topEdges} EDGES / NODE</span>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={topEdges}
                  onChange={(event) => setTopEdges(Number(event.target.value))}
                />
              </label>
              <span className="terminal-panel-meta">
                FORCE: {layoutInfo?.forceTicks ?? "—"} / LABEL OVERLAPS:{" "}
                {layoutInfo?.labelOverlapCount ?? "—"}
              </span>
            </div>
            <div className="network-canvas-wrap">
              <div
                ref={container}
                aria-label="correlation minimum spanning tree"
                className="network-canvas"
              />
              {data && data.nodes.length > 0 && (
                <>
                  <div className="network-sector-legend" aria-label="Sector legend">
                    <div className="network-legend-heading">
                      SECTORS / CLICK TO TOGGLE
                    </div>
                    {sectors.map((sector) => {
                      const isHidden = hiddenSectors.includes(sector.name);
                      return (
                        <button
                          key={sector.name}
                          type="button"
                          className="network-legend-item"
                          data-hidden={isHidden || undefined}
                          onClick={() =>
                            setHiddenSectors((current) =>
                              current.includes(sector.name)
                                ? current.filter((name) => name !== sector.name)
                                : [...current, sector.name],
                            )
                          }
                        >
                          <span
                            className="network-legend-swatch"
                            style={{ backgroundColor: sector.color }}
                          />
                          <span>{sector.name}</span>
                          <span className="numeric">{sector.count}</span>
                        </button>
                      );
                    })}
                  </div>
                  <div className="network-map-key" aria-hidden="true">
                    <span>● NODE AREA / CONNECTIONS</span>
                    <span>— EDGE / CORRELATION STRENGTH</span>
                    <span>
                      {topology?.componentCount ?? 0}
                      {topology?.componentCount === 1 ? " TREE" : " TREES"} / MIN{" "}
                      {Math.round(layoutInfo?.minimumNodeDistance ?? 0)}PX
                    </span>
                  </div>
                </>
              )}
              {hovered && (
                <div
                  className="network-tooltip"
                  style={{ left: hovered.x + 12, top: hovered.y + 12 }}
                >
                  <strong>{companyNames[hovered.symbol] ?? hovered.symbol}</strong>
                  <span>{hovered.symbol}</span>
                  <span>{hovered.industry}</span>
                  <span>
                    {hovered.degree} CONNECTION{hovered.degree === 1 ? "" : "S"}
                  </span>
                </div>
              )}
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
