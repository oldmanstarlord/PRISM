# Step 13 Historical Score Validation Specification

Status: implemented; empirical run pending clean production inputs. The validation
configuration is `validation_parameters:1.0.0` and remains `draft`.

## Scope and guardrails

This module tests descriptive risk ordering. It is not a price forecast, trading
strategy, or investment recommendation. Historical scoring uses current NIFTY 200
membership because historical constituents are unavailable, so every historical
result and the validation UI carries an explicit survivorship-bias warning.

All score inputs obey the score engine's point-in-time cutoff. Labels are separate:
they use the as-of adjusted close and exactly the next 20 observed trading-session
closes. A price on or before the as-of date cannot enter a forward return except for
the as-of close that anchors the first return.

## Configured assumptions

The following are ASSUMPTIONS pending owner approval and are stored in the draft
configuration rather than hidden in code:

- month-end scoring frequency: one observation per calendar month;
- target horizon: 20 trading sessions; worst-return window: 5 sessions;
- minimum cross-section: 5 securities;
- expanding walk-forward split: 12 training periods, 1-period embargo, 3 test
  periods, advancing by 3 periods;
- confidence bins: `[0, 40)`, `[40, 60)`, `[60, 80)`, `[80, 101)`;
- deterministic random baseline seed: `13013`;
- Layer 1 comparison bands: absolute 1, 2, and 3 sigma.

## Target calculations

For log returns `r` from the as-of close through the next 20 closes:

- realised volatility = sample standard deviation of the 20 log returns multiplied
  by `sqrt(252)`;
- maximum drawdown = maximum peak-to-trough percentage loss over the as-of close
  and the next 20 closes;
- worst five-day return = minimum compounded return across every consecutive
  five-session window in those 20 returns.

Missing an as-of close or any of the 20 future sessions makes all targets for that
stock/date unavailable. No partial label is substituted.

## Evaluation

Only test dates emitted by `backend/app/validation/splits.py` are evaluated. Within
each test date, metrics are cross-sectional Spearman rank correlation (average ranks
for ties), top-minus-bottom decile target spread, and top/bottom quintile realised
risk. Aggregate correlation is the arithmetic mean of valid per-period
correlations. The score is compared independently with trailing-volatility rank,
beta rank, and a deterministic random rank. Worst-five-day returns are sign-reversed
only when deciding whether a risk rank is better; stored raw target metrics remain
auditable.

Confidence calibration reports Spearman correlation and normalized absolute rank
error in every configured confidence bin. A run records a failure when the highest
populated confidence bin is not more reliable than the lowest populated bin.

Each active component and dimension is excluded through the Step 12 ablation hook.
The change in mean test-period Spearman is stored for every target. A component is
recommended `keep` only when removing it worsens the mean oriented result; weights
are never changed automatically.

Layer 1 divergence values are not modified. Empirical absolute-band exceedance
rates are compared with the standard-normal two-sided reference
`erfc(band / sqrt(2))` for each existing horizon.

Every attempted full score, baseline, component ablation, and dimension ablation is
recorded in `experiment_log`. The implementation exposes no trading-style metric,
so trial-count adjustment is marked not applicable. If one is later added, its
multiple-testing adjustment must be versioned and configured before display.

## Persistence and idempotency

`validation_run` is unique by kind, effective configuration fingerprint, and
period. The fingerprint includes both model-config checksums, active component
metadata, and the ablation flag. An identical rerun reuses its completed record.
Scalar evidence is stored in `validation_result`; failures and limitations are
retained in run notes and shown plainly by the API and frontend.
