"""Point-in-time feature extraction for risk models."""

import numpy as np
import pandas as pd  # type: ignore[import-untyped]


def compute_ewma_volatility(
    returns: pd.Series, decay: float = 0.94, annualize: bool = True
) -> pd.Series:
    """Compute RiskMetrics EWMA volatility series with recursive point-in-time formula.

    sigma_t^2 = decay * sigma_{t-1}^2 + (1 - decay) * r_t^2
    """
    arr = returns.values
    n = len(arr)
    if n == 0:
        return pd.Series(dtype=float, index=returns.index)

    var = np.zeros(n, dtype=float)
    var[0] = arr[0] ** 2

    one_minus_decay = 1.0 - decay
    for t in range(1, n):
        var[t] = decay * var[t - 1] + one_minus_decay * (arr[t] ** 2)

    vol = np.sqrt(var)
    if annualize:
        vol = vol * np.sqrt(252.0)

    return pd.Series(vol, index=returns.index)


def compute_realized_volatility(
    returns: pd.Series, window: int = 21, annualize: bool = True
) -> pd.Series:
    """Trailing realized sample volatility over a rolling window.

    sigma_{t, window} = sqrt(252 * sum(R_t^2) / window)
    """
    sq_ret = returns**2
    # Rolling sum of squared daily returns
    roll_var = sq_ret.rolling(window=window, min_periods=window).mean()
    vol = np.sqrt(roll_var)
    if annualize:
        vol = vol * np.sqrt(252.0)
    return vol


def compute_forward_realized_volatility(
    returns: pd.Series, horizon: int = 21, annualize: bool = True
) -> pd.Series:
    """Compute forward-looking realized volatility over [t+1, t+horizon].

    Used exclusively as target label y during training and evaluation.
    Never used as a feature at date t.
    """
    sq_ret = returns**2
    # Exact [t+1, t+horizon] window. Incomplete tail labels remain missing.
    fwd_var = sq_ret.shift(-1).rolling(window=horizon, min_periods=horizon).mean()
    fwd_var = fwd_var.shift(-(horizon - 1))
    vol = np.sqrt(fwd_var)
    if annualize:
        vol = vol * np.sqrt(252.0)
    return vol


def compute_forward_max_drawdown(prices: pd.Series, horizon: int = 21) -> pd.Series:
    """Compute forward maximum drawdown over [t+1, t+horizon]."""
    p = prices.values
    n = len(p)
    mdd = np.full(n, np.nan, dtype=float)

    for i in range(n):
        end = i + 1 + horizon
        if end > n:
            continue
        window_prices = p[i + 1 : end]
        # Include current price p[i] as peak reference
        all_prices = np.concatenate(([p[i]], window_prices))
        peaks = np.maximum.accumulate(all_prices)
        dds = (all_prices - peaks) / np.maximum(peaks, 1e-6)
        mdd[i] = float(np.min(dds))

    return pd.Series(mdd, index=prices.index)


def build_volatility_features(
    prices: pd.Series,
    benchmark_returns: pd.Series | None = None,
    volumes: pd.Series | None = None,
) -> pd.DataFrame:
    """Build point-in-time feature matrix for volatility forecasting.

    All features at date t use strictly information <= t.
    """
    simple_returns = prices.pct_change(fill_method=None).dropna()
    dates = simple_returns.index

    # 1. Trailing realized volatilities across multiple scales (HAR structure)
    vol_1d = (np.abs(simple_returns) * np.sqrt(252.0)).rename("vol_1d")
    vol_5d = compute_realized_volatility(simple_returns, window=5).rename("vol_5d")
    vol_21d = compute_realized_volatility(simple_returns, window=21).rename("vol_21d")
    vol_63d = compute_realized_volatility(simple_returns, window=63).rename("vol_63d")

    # 2. EWMA volatility (lambda = 0.94)
    ewma_vol = compute_ewma_volatility(simple_returns, decay=0.94).rename("vol_ewma_94")

    # 3. Higher return moments (21-day rolling)
    roll_mean = simple_returns.rolling(21, min_periods=10).mean()
    roll_std = simple_returns.rolling(21, min_periods=10).std()
    ret_skew = (
        (((simple_returns - roll_mean) / np.maximum(roll_std, 1e-6)) ** 3)
        .rolling(21, min_periods=10)
        .mean()
        .rename("return_skew_21d")
    )
    ret_kurt = (
        (((simple_returns - roll_mean) / np.maximum(roll_std, 1e-6)) ** 4)
        .rolling(21, min_periods=10)
        .mean()
        .rename("return_kurt_21d")
    )

    # 4. Downside volatility ratio
    down_returns = np.minimum(simple_returns, 0.0)
    down_var = (down_returns**2).rolling(21, min_periods=10).mean()
    down_vol = (np.sqrt(down_var) * np.sqrt(252.0)).rename("downside_vol_21d")
    downside_ratio = (down_vol / np.maximum(vol_21d, 1e-6)).rename("downside_ratio")

    features = [
        vol_1d,
        vol_5d,
        vol_21d,
        vol_63d,
        ewma_vol,
        ret_skew,
        ret_kurt,
        downside_ratio,
    ]

    # 5. Volume features if provided
    if volumes is not None and not volumes.empty:
        vol_aligned = volumes.reindex(dates)
        sma_20 = vol_aligned.rolling(20, min_periods=20).mean()
        vol_spike = (vol_aligned / sma_20.replace(0, np.nan)).rename("volume_spike_20d")
        features.append(vol_spike)

    # 6. Benchmark volatility context
    if benchmark_returns is not None and not benchmark_returns.empty:
        b_aligned = benchmark_returns.reindex(dates)
        b_vol_21d = compute_realized_volatility(b_aligned, window=21).rename("benchmark_vol_21d")
        features.append(b_vol_21d)

    df_features = pd.concat(features, axis=1)
    return df_features.dropna()


def build_anomaly_features(
    prices: pd.Series,
    benchmark_returns: pd.Series | None = None,
    volumes: pd.Series | None = None,
) -> pd.DataFrame:
    """Build features for holding-level anomaly and outlier detection.

    Features:
    1. return_zscore_60d: Z-score of daily return relative to 60-day window.
    2. volume_spike_20d: Ratio of volume to 20-day SMA.
    3. vol_ratio_5_20: Short-term volatility surge (5d vol / 20d vol).
    4. benchmark_divergence: Daily return minus benchmark return.
    """
    simple_returns = prices.pct_change(fill_method=None).dropna()
    dates = simple_returns.index

    # 1. 60-day return z-score
    roll_mean = simple_returns.rolling(60, min_periods=15).mean()
    roll_std = simple_returns.rolling(60, min_periods=15).std()
    ret_zscore = ((simple_returns - roll_mean) / np.maximum(roll_std, 1e-6)).rename(
        "return_zscore_60d"
    )

    # 2. 5d vs 20d volatility ratio
    vol_5d = compute_realized_volatility(simple_returns, window=5)
    vol_20d = compute_realized_volatility(simple_returns, window=20)
    vol_ratio = (vol_5d / np.maximum(vol_20d, 1e-6)).rename("vol_ratio_5_20")

    # 3. Volume spike ratio
    if volumes is not None and not volumes.empty:
        vol_aligned = volumes.reindex(dates)
        sma_20 = vol_aligned.rolling(20, min_periods=20).mean()
        vol_spike = (vol_aligned / sma_20.replace(0, np.nan)).rename("volume_spike_20d")
    else:
        vol_spike = None

    # 4. Benchmark divergence
    if benchmark_returns is not None and not benchmark_returns.empty:
        b_aligned = benchmark_returns.reindex(dates)
        bench_div = (simple_returns - b_aligned).rename("benchmark_divergence")
    else:
        bench_div = None

    features = [ret_zscore, vol_ratio]
    if vol_spike is not None:
        features.append(vol_spike)
    if bench_div is not None:
        features.append(bench_div)
    df = pd.concat(features, axis=1)
    return df.dropna()
