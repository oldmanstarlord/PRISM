# MST Explanation Specification v1

## Scope and invariants

Step E2 adds evidence-bound explanations for a stored raw Layer 2 MST edge, any
pair connected through that tree, and a node. It reads Layer 2 outputs and stored
point-in-time prices; it does not change `correlation-mst-v1`, its calculation,
window, thresholds, or deterministic tie-break.

All sentences are deterministic templates from draft
`mst_explain_templates:1.2.0`. Unsupported sentences are omitted and a limitation
is added. Every rendered sentence cites one or more evidence IDs. The standard
non-advice disclaimer and D3 result-envelope fields are included on every payload.

## Evidence and calculations

- Direct co-movement uses paired, non-imputed log returns within the stored run
  window. The displayed distance is `sqrt(2 * (1 - rho))` and is checked against
  the persisted edge distance for adjacent pairs.
- The accepted Kruskal step is the persisted `edge_rank`. Group sizes are
  deterministically reconstructed by replaying accepted edges in rank order; a
  cycle, missing rank, or a tree other than `N - 1` edges fails closed.
- Neighbour rank is each endpoint's rank among all stored pairwise correlations.
- Industry, cluster, cluster-rule version, degree, centrality, and cluster size are
  read from stored run diagnostics when present.
- Persistence is the share of the configured last 26 completed raw windows that
  contain the unordered edge. Minimum, median, and maximum co-movement values are
  recomputed from stored prices for those windows.
- Residual evidence uses the existing Layer 2 market-residual input function and
  reports whether the edge also occurs in the matching residual tree.
- Macro similarity is cosine similarity between significant stored industry
  sensitivity vectors. A shared driver is shown only when it is significant for
  both industries.
- Historical beta and R-squared reuse the shock engine's regression function. The
  wording is descriptive and does not create a composite impact score.
- Event/news co-occurrence uses stored items within the configured 90-day lookback
  and is omitted when the required linked evidence is absent.
- Pair explanations use the unique stored tree path, hop count, each link's rho and
  distance, the weakest link by lowest rho, and the direct pair statistic.
- Chart specs contain a 60-session rolling co-movement series and a downsampled
  paired-return scatter. They are data payloads, not predictions.

## API and UI

- `GET /api/v1/explain/mst/edge?run_id=&a=&b=`
- `GET /api/v1/explain/mst/node/{symbol}`
- `GET /api/v1/explain/mst/pair?a=&b=`

The MST page opens the shared ExplainDrawer from edge and node selections, provides
a pair search, and renders config-provided distance/thickness legends and a
stability badge. Optional `portfolio_id` enriches edge impact with stored weights
and risk contributions without altering the MST explanation.

## Explicit assumptions and limitations

- **ASSUMPTION:** degree one is labelled `leaf`; degree greater than one is labelled
  `hub` for plain-language display. This label is not a causal or systemic-risk
  classification and awaits owner wording approval.
- **ASSUMPTION:** empirical weighted-centrality percentile is the share of stored
  node values less than or equal to the subject value.
- A tree retains only `N - 1` links, so absence of a direct edge does not imply no
  statistical relationship.
- The current production raw run has edges and nodes but lacks cluster, node-metric,
  and rolling-stability diagnostics. Those sections are therefore omitted with
  explicit limitations until the existing diagnostics job is run.
- Co-movement, beta, path position, centrality, and event overlap do not prove a
  business relationship, causality, or a future effect.

