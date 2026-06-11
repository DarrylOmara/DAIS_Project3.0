import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import HuberRegressor

# ------------------------------------------------------------
# HIGH-SPEED INTRA-DAY TRUE BETA ENGINE
# ------------------------------------------------------------
def compute_true_beta(asset_close, benchmark_close):
    """
    Computes a stable, blended 'true beta' using cross-sectional alignment.
    Optimized for dense high-frequency intraday returns.
    """
    # Vectorized inner intersection lock
    df = pd.concat([asset_close, benchmark_close], axis=1).dropna()
    df.columns = ['asset', 'bench']
    
    if len(df) < 20:
        return 1.0  # Fallback to standard market unit beta
        
    daily = df.pct_change().dropna()
    if daily.empty:
        return 1.0

    # Extract clean numpy structures
    y = daily['asset'].to_numpy()
    X = daily['bench'].to_numpy()

    # 1. Full Dataset OLS Baseline Slope Tracker
    try:
        beta_ols, _, _, _, _ = stats.linregress(X, y)
    except Exception:
        beta_ols = np.nan

    # 2. Short Term Momentum Slice Lookback (Last 500 Intraday Bars)
    if len(daily) >= 500:
        try:
            beta_short, _, _, _, _ = stats.linregress(X[-500:], y[-500:])
        except Exception:
            beta_short = np.nan
    else:
        beta_short = beta_ols

    # 3. Robust Linear Estimator (Scaled Z-Space Huber Regression)
    try:
        X_mat = X.reshape(-1, 1)
        x_scale = X_mat.std()
        if x_scale > 0:
            X_scaled = X_mat / x_scale
            huber = HuberRegressor(epsilon=1.35, max_iter=500).fit(X_scaled, y)
            beta_robust = huber.coef_[0] / x_scale
        else:
            beta_robust = np.nan
    except Exception:
        beta_robust = np.nan

    # Dynamic Weight Assignment Structure
    betas = np.array([beta_ols, beta_short, beta_robust], dtype=float)
    weights = np.array([0.50, 0.30, 0.20])
    
    mask = ~np.isnan(betas)
    if mask.sum() == 0:
        return 1.0
        
    beta_true = np.sum(betas[mask] * weights[mask]) / np.sum(weights[mask])
    return float(beta_true)

# ------------------------------------------------------------
# HIGH-FREQUENCY PERFORMANCE METRICS
# ------------------------------------------------------------
def performance_metrics_from_ledger(ledger_df, price_series):
    """
    Calculates institutional risk-adjusted metrics for intraday portfolios.
    Eliminates empty day resampling traps to ensure accurate tracking.
    """
    if ledger_df.empty:
        return {"total_return": 0.0, "annualized_return": 0.0, "annualized_vol": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
        
    # Sort and extract total portfolio equity values
    ledger_sorted = ledger_df.sort_values('Date')
    timestamps = pd.to_datetime(ledger_sorted['Date']).to_numpy()
    equity_curve = ledger_sorted['Total_Value'].to_numpy(dtype=np.float64)
    
    if len(equity_curve) < 2:
        return {"total_return": 0.0, "annualized_return": 0.0, "annualized_vol": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}

    # Total Return Calculation
    initial_value = equity_curve[0]
    final_value = equity_curve[-1]
    total_return = (final_value / initial_value) - 1.0 if initial_value > 0 else 0.0
    
    # UPGRADED PATCH: Calculate geometric annualized returns based on precise time differences
    duration_ns = timestamps[-1] - timestamps[0]
    
    # Safely convert timedelta object variants into plain float raw nanosecond counts
    if isinstance(duration_ns, np.timedelta64):
        total_ns = float(duration_ns / np.timedelta64(1, 'ns'))
    else:
        total_ns = float(duration_ns.total_seconds() * 1_000_000_000)
        
    duration_years = total_ns / (365.25 * 24 * 60 * 60 * 1_000_000_000)
    
    if duration_years > 0 and initial_value > 0 and final_value > 0:
        ann_return = (final_value / initial_value) ** (1.0 / duration_years) - 1.0
    else:
        ann_return = 0.0

    # Calculate Intraday Volatility
    pct_changes = np.diff(equity_curve) / equity_curve[:-1]
    
    # Track the average number of bars per day to scale volatility accurately
    unique_days = np.unique(timestamps.astype('datetime64[D]'))
    n_days = len(unique_days) if len(unique_days) > 0 else 1
    bars_per_day = len(equity_curve) / n_days
    
    # Scale interval volatility to an annualized standard deviation
    interval_vol = pct_changes.std() if len(pct_changes) > 0 else 0.0
    ann_vol = interval_vol * np.sqrt(bars_per_day * 252)

    # Sharpe Calculation assuming a standard baseline risk-free cash yield (4.0%)
    risk_free = 0.04
    excess_return = ann_return - risk_free
    
    if ann_vol > 0:
        sharpe = excess_return / ann_vol
    else:
        sharpe = 0.0 if excess_return <= 0 else float('inf')

    # Max Drawdown Array Scan
    running_peaks = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve / running_peaks) - 1.0 if len(running_peaks) > 0 else np.array([0.0])
    max_dd = drawdowns.min()

    return {
        "total_return": float(total_return),
        "annualized_return": float(ann_return),
        "annualized_vol": float(ann_vol),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd)
    }
