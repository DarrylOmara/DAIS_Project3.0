import os
import time
import logging
import yaml
import matplotlib
matplotlib.use("Agg")  # Force non-GUI backend globally to maximize thread speed

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from src.src.data_fetcher import fetch_daily, compute_mas
from src.src.daist_engine import DAISTradingEngine
from src.src.metrics import compute_true_beta, performance_metrics_from_ledger
from src.src.charts import make_all_charts
from src.src.report_generator import build_pdf_report
from src.src.pptx_builder import build_presentation
from src.src.dashboard_export import build_dashboard_html
from src.src.docx_guide import build_docx_guide
from src.src.trade_reporter import generate_trade_report, generate_trade_summary, format_trade_summary_for_display

# ------------------------------------------------------------
# HIGH-PERFORMANCE LOGGING INITIALIZATION
# ------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s",
)
logger = logging.getLogger("DAIS_Intraday")

def load_config(config_path: str = "config.yaml"):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

# ------------------------------------------------------------
# HIGH-SPEED TICKER PIPELINE WORKER
# ------------------------------------------------------------
def run_for_ticker(ticker: str, cfg: dict, benchmark_close: pd.Series, outdir: str):
    start = time.time()
    logger.info(f"Processing high-frequency matrix for {ticker}")
    try:
        data_dir = cfg.get("data_dir", "data")
        df_path = os.path.join(data_dir, f"{ticker}.csv")

        # High-speed data loading with explicit timestamp parsing
        if os.path.exists(df_path):
            try:
                df = pd.read_csv(df_path, parse_dates=["Date"]).set_index("Date").sort_index()
            except Exception:
                # Try reading CSVs that were saved with the date as the index
                df = pd.read_csv(df_path, parse_dates=True, index_col=0)
                df.index.name = "Date"
                df = df.sort_index()
        else:
            # Attempt to auto-download intraday bars first, then fall back to daily
            try:
                logger.info(f"Local file {df_path} missing; attempting auto-download intraday for {ticker}")
                intraday_interval = cfg.get("bar_interval", cfg.get("intraday_interval", "1m"))
                intraday_days = int(cfg.get("intraday_lookback_days", cfg.get("lookback_days", 7)))
                try:
                    df = fetch_intraday(ticker, interval=intraday_interval, period_days=intraday_days, data_dir=cfg.get("data_dir", "data"))
                except Exception:
                    logger.info(f"Intraday fetch failed for {ticker}; falling back to daily series")
                    df = fetch_daily(ticker, cfg.get("lookback_days", 30), data_dir=cfg.get("data_dir", "data"))
            except Exception as e:
                raise FileNotFoundError(f"Missing intraday data asset: {df_path}") from e

        # 1. Compute technical indicators (EMA/MA)
        df = compute_mas(df)

        # 2. Strict index alignment to calculate the true beta metric
        # Use an inner join to ensure timestamps match the benchmark exactly
        aligned = df.join(benchmark_close.rename("Bench_Close"), how="inner")
        if not aligned.empty:
            beta_true = compute_true_beta(aligned["Close"], aligned["Bench_Close"])
        else:
            beta_true = float("nan")

        beta_use = cfg.get("beta_default", 1.0) if pd.isna(beta_true) else beta_true

        # 3. Initialize High-Frequency Execution Engine
        engine = DAISTradingEngine(
            beta=beta_use,
            initial_capital=cfg["initial_capital"],
            core_buy_amt=cfg["core_buy_amt"],
            base_buy_amt=cfg.get("base_buy_amt", 250.0),       # Dollar amount for incremental buys
            base_sell_amt=cfg.get("base_sell_amt", 250.0),     # Dollar amount for profit-taking
            inventory_floor_amt=cfg.get("inventory_floor_amt", 100.0),  # Minimum inventory in dollars
        )

        # Execute the optimized backtest loop
        ledger = engine.run_backtest(df, cfg)

        # Local output path structures
        ticker_outdir = os.path.join(outdir, ticker)
        os.makedirs(ticker_outdir, exist_ok=True)

        # Export performance telemetry
        ledger_csv = os.path.join(ticker_outdir, f"{ticker}_ledger.csv")
        ledger.to_csv(ledger_csv, index=False)

        metrics = performance_metrics_from_ledger(ledger, df["Close"])
        metrics_csv = os.path.join(ticker_outdir, f"{ticker}_metrics.csv")
        pd.DataFrame([metrics]).to_csv(metrics_csv, index=False)

        # Generate trade reports
        trades_df = engine.get_trades_dataframe()
        trades_csv = generate_trade_report(ticker, trades_df, ticker_outdir)
        trade_summary = generate_trade_summary(ticker, trades_df, ticker_outdir)
        logger.info(format_trade_summary_for_display(trade_summary))

        # Generate diagnostic charts
        charts = make_all_charts(ticker, df, ledger, ticker_outdir)

        elapsed = time.time() - start
        logger.info(f"Completed {ticker} intraday backtest [{len(df)} rows] in {elapsed:.2f}s")

        return {
            "ticker": ticker,
            "metrics": metrics,
            "beta_true": beta_true,
            "sell_rule_stats": getattr(engine, "sell_rule_stats", {}),
            "trade_stats": getattr(engine, "trade_stats", {}),
            "ledger_csv": ledger_csv,
            "trades_csv": trades_csv,
            "trade_summary": trade_summary,
            "charts": charts,
        }

    except Exception as e:
        logger.error(f"Execution fault inside ticker thread {ticker}: {e}", exc_info=True)
        return {
            "ticker": ticker, "metrics": {}, "beta_true": float("nan"),
            "sell_rule_stats": {}, "trade_stats": {}, "ledger_csv": "",
            "trades_csv": "", "trade_summary": {}, "charts": {}, "error": str(e),
        }

# ------------------------------------------------------------
# PIPELINE ORCHESTRATOR
# ------------------------------------------------------------
def main():
    cfg = load_config()

    # Extract destination paths, defaulting to standard outputs if empty
    outdir = cfg.get("output_dir", "outputs/DAIS_Deliverables")
    os.makedirs(outdir, exist_ok=True)

    tickers = cfg.get("tickers", [])
    benchmark = cfg.get("benchmark", "NASDAQ")

    # Map friendly benchmark names to actual fetch tickers (use NASDAQ composite '^IXIC')
    fetch_benchmark = benchmark
    if isinstance(benchmark, str) and benchmark.strip().upper() in ("NASDAQ", "NASDAQCOM", "NASDAQCOMPOSITE"):
        fetch_benchmark = "^IXIC"

    logger.info(f"Loading intraday benchmark reference series: {benchmark} (fetching {fetch_benchmark})")
    # Attempt to fetch benchmark series, with safe fallbacks if the ticker is invalid
    benchmark_df = None
    try:
        benchmark_df = fetch_daily(
            fetch_benchmark, cfg.get("lookback_days", 30), data_dir=cfg.get("data_dir", "data")
        )
    except Exception as e:
        logger.warning(f"Primary benchmark fetch failed for {benchmark}: {e}")
        # Try common alternate benchmark tickers (SPY removed per request)
        for alt in ["^IXIC", "^GSPC"]:
            try:
                logger.info(f"Attempting fallback benchmark: {alt}")
                benchmark_df = fetch_daily(alt, cfg.get("lookback_days", 30), data_dir=cfg.get("data_dir", "data"))
                benchmark = alt
                logger.info(f"Using fallback benchmark: {alt}")
                break
            except Exception:
                logger.debug(f"Fallback {alt} failed", exc_info=True)

    if benchmark_df is None or benchmark_df.empty:
        logger.error("Unable to obtain benchmark price series; aborting run.")
        raise SystemExit("Benchmark data fetch failed")
    benchmark_close = benchmark_df.sort_index()["Close"]

    summary = []
    max_workers = min(int(cfg.get("max_workers", 4)), len(tickers))

    logger.info(f"Spawning thread workers (Count: {max_workers}) across data frames...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_for_ticker, ticker, cfg, benchmark_close, outdir): ticker
            for ticker in tickers
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing Assets"):
            summary.append(future.result())

    logger.info("Intraday processing batch finished. Assembling documentation suites...")

    # Exception-isolated documentation generator loops
    for builder_func, name in [
        (lambda: build_pdf_report(summary, cfg, outdir), "PDF Report Summary"),
        (lambda: build_presentation(summary, cfg, outdir), "PPTX Slide Deck"),
        (lambda: build_dashboard_html(summary, cfg, outdir), "HTML Interactive Dashboard"),
        (lambda: build_docx_guide(cfg, outdir), "DOCX Operational Manual")
    ]:
        try:
            path = builder_func()
            logger.info(f"Generated {name} at: {path}")
        except Exception as e:
            logger.error(f"Failed to generate documentation asset [{name}]: {e}", exc_info=True)

    logger.info("High-Frequency DAIS pipeline sequence terminated cleanly.")

if __name__ == "__main__":
    main()
