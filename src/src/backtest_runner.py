import os
import pandas as pd

from src.data_fetcher import fetch_daily, compute_mas
from src.daist_engine import DAISTradingEngine
from src.metrics import compute_true_beta, performance_metrics_from_ledger


def run_for_ticker(ticker, spy_close_series, cfg, outdir):
    """
    Runs the full DAIS pipeline for a single ticker:
    - Fetch data
    - Compute moving averages
    - Compute true beta
    - Run DAIS engine
    - Save ledger + metrics
    - Return summary for reporting
    """

    # ------------------------------------------------------------
    # FETCH DATA
    # ------------------------------------------------------------
    df = fetch_daily(
        ticker,
        period_years=cfg['period_years'],
        data_dir=cfg.get('data_dir', 'data')
    )
    df = compute_mas(df)

    # ------------------------------------------------------------
    # TRUE BETA CALCULATION
    # ------------------------------------------------------------
    beta_true = compute_true_beta(df['Close'], spy_close_series)

    # Fallback to config default if needed
    beta_use = beta_true if not pd.isna(beta_true) else cfg['beta_default']

    # ------------------------------------------------------------
    # INITIALIZE DAIS ENGINE
    # ------------------------------------------------------------
    engine = DAISTradingEngine(
        beta=beta_use,
        initial_capital=cfg['initial_capital'],
        core_buy_amt=cfg['core_buy_amt'],
        base_buy=cfg['base_buy'],
        base_sell=cfg['base_sell'],
        inventory_floor=cfg['inventory_floor']
    )

    # ------------------------------------------------------------
    # RUN BACKTEST
    # ------------------------------------------------------------
    ledger = engine.run_backtest(df)

    # ------------------------------------------------------------
    # OUTPUT DIRECTORY FOR THIS TICKER
    # ------------------------------------------------------------
    ticker_outdir = os.path.join(outdir, ticker)
    os.makedirs(ticker_outdir, exist_ok=True)

    # ------------------------------------------------------------
    # SAVE LEDGER
    # ------------------------------------------------------------
    ledger_csv = os.path.join(ticker_outdir, f"{ticker}_ledger.csv")
    ledger.to_csv(ledger_csv, index=False)

    # ------------------------------------------------------------
    # PERFORMANCE METRICS
    # ------------------------------------------------------------
    metrics = performance_metrics_from_ledger(ledger, df['Close'])

    metrics_csv = os.path.join(ticker_outdir, f"{ticker}_metrics.csv")
    pd.DataFrame([metrics]).to_csv(metrics_csv, index=False)

    # ------------------------------------------------------------
    # RETURN SUMMARY FOR REPORT GENERATION
    # ------------------------------------------------------------
    return {
        "ticker": ticker,
        "metrics": metrics,
        "beta_true": beta_true,
        "ledger_csv": ledger_csv
    }
