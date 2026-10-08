# Phase 1 Portfolio Contract

## Scope

Phase 1 accepts private, authenticated NIFTY 200 portfolios and produces daily
closing-price analytics. It is not an order-management system, live intraday monitor or
investment recommendation service.

## Approved input policy

- A portfolio declares exactly one input mode: `quantities` or `weights`.
- A portfolio may contain up to 200 distinct active NIFTY 200 securities.
- Symbols outside the active NIFTY 200 universe are rejected.
- Duplicate symbols are combined before validation.
- `CASH` is accepted as a non-negative INR cash amount or portfolio weight.
- Short positions and non-positive security values are rejected.
- Weight portfolios must total 1.0 including cash, within a tolerance of 0.0001.
- Quantity portfolios are valued on the latest closing date common to every holding.
- Uploads must pass a preview. Saving requires the preview fingerprint, preventing a
  changed payload from being silently persisted.
- CSV input has two columns: `symbol,value`. Weight values are decimal fractions, not
  percentages; for example, 25% is entered as `0.25`.

## Identity and ownership

- Supabase Auth supplies the user identity.
- The FastAPI service verifies every bearer token through Supabase Auth.
- Every portfolio, snapshot and holding carries the immutable owner UUID.
- API queries always filter by the authenticated owner.
- PostgreSQL row-level-security policies provide defense in depth for direct Supabase
  Data API access.
- Anonymous access to portfolio tables is not granted.

## Persistence

- `portfolio` stores identity, owner, input mode, currency and archive state.
- `portfolio_snapshot` stores a dated, immutable holdings snapshot and deterministic
  input fingerprint.
- `portfolio_snapshot_holding` stores one positive quantity or target weight per security.
- The independently developed `portfolio_holding` table remains intact for its original
  analytics workflow; the two schemas are deliberately not conflated.
- `audit_event` stores owner-scoped create, archive, restore and delete events without copying
  raw CSV content or credentials. Deleted-portfolio events remain as audit evidence.
- Portfolios are archived before optional permanent deletion.
- Phase 1 stores snapshots, not transactions, dividends or cash-flow history.

## Implemented analytics

- Position and industry weights, concentration, annualized volatility and drawdown.
- Layer 1 divergence annotations for owned securities.
- Layer 2 MST paths, bridge stocks, clusters, subtree visualization and consecutive-window
  stability confidence.
- Selected-security regression-beta shocks and parallel selected-industry shocks.

Analytics must expose valuation date, price coverage, assumptions, exclusions and data
freshness. Missing values are never replaced with invented prices or returns.

## First vertical-slice acceptance

1. A user can sign in through Supabase Auth.
2. A CSV can be parsed and previewed without writing to the database.
3. Invalid, unsupported and inconsistent rows are explained before confirmation.
4. A confirmed preview creates a private portfolio and immutable dated snapshot.
5. The owner can list and reload the saved portfolio.
6. Another authenticated user cannot read, alter or delete it.
7. Archive precedes permanent deletion.
