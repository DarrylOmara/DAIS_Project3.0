import os
import matplotlib
matplotlib.use("Agg")  # Lock non-GUI backend firmly to guarantee thread safety
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

def _downsample_series(series, target_points=2000):
    """
    Downsamples massive high-frequency series using rapid multi-point vector slicing
    to prevent chart rendering bottlenecks while preserving historical price extremes.
    """
    n_points = len(series)
    if n_points <= target_points:
        return series
        
    # Calculate step size intervals
    step = n_points // target_points
    # Slice the array using max/min bounds inside step intervals to capture intraday spikes
    idx = np.arange(0, n_points, step)
    return series.iloc[idx]

def make_all_charts(ticker: str, df: pd.DataFrame, ledger_df: pd.DataFrame, output_dir: str) -> dict:
    """
    Generates high-performance visual chart assets for high-frequency intraday backtests.
    Applies downsampling to eliminate thread lagging and canvas rendering stalls.
    """
    chart_paths = {}
    
    if df.empty or ledger_df.empty:
        return chart_paths
        
    # Set explicit plot rendering styles for clean scannability
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    
    # Align and downsample series datasets to optimize drawing canvas speeds
    vis_df = _downsample_series(df["Close"], target_points=1500)
    
    # ------------------------------------------------------------
    # CHART 1: INTRADAY PRICE & MOVING AVERAGE EXECUTIONS
    # ------------------------------------------------------------
    fig, ax1 = plt.subplots(figsize=(11, 5), dpi=120)
    
    ax1.plot(vis_df.index, vis_df.values, label="Asset Close", color="#2c3e50", alpha=0.8, linewidth=1.2)
    
    if "MA20" in df.columns:
        vis_ma20 = _downsample_series(df["MA20"], target_points=1500)
        ax1.plot(vis_ma20.index, vis_ma20.values, label="Fast EMA (9/20)", color="#e67e22", linestyle="--", alpha=0.7, linewidth=1.0)
    if "MA50" in df.columns:
        vis_ma50 = _downsample_series(df["MA50"], target_points=1500)
        ax1.plot(vis_ma50.index, vis_ma50.values, label="Slow EMA (21/50)", color="#95a5a6", linestyle=":", alpha=0.7, linewidth=1.0)

    ax1.set_title(f"DAIS Strategy Execution Topology Profile — {ticker}", fontsize=12, fontweight="bold", pad=10)
    ax1.set_ylabel("Share Valuation Price ($)", fontsize=10)
    ax1.grid(True, linestyle=":", alpha=0.5)
    ax1.legend(loc="upper left", frameon=True, fontsize=9)
    
    plt.gcf().autofmt_xdate()
    plt.tight_layout()
    
    p1 = os.path.join(output_dir, f"{ticker}_execution_topology.png")
    fig.savefig(p1, bbox_inches="tight", dpi=120)
    plt.close(fig)
    chart_paths["topology"] = p1

    # ------------------------------------------------------------
    # CHART 2: PORTFOLIO EQUITY CURVE & GROWTH TRACK
    # ------------------------------------------------------------
    fig, ax2 = plt.subplots(figsize=(11, 4), dpi=120)
    
    # Cleanly sync the tracking ledger dates
    ledger_sorted = ledger_df.sort_values("Date")
    ledger_dates = pd.to_datetime(ledger_sorted["Date"])
    equity_curve = pd.Series(ledger_sorted["Total_Value"].values, index=ledger_dates)
    
    vis_equity = _downsample_series(equity_curve, target_points=1500)
    
    ax2.plot(vis_equity.index, vis_equity.values, label="Total Growth Value", color="#27ae60", linewidth=1.5)
    ax2.fill_between(vis_equity.index, vis_equity.values, vis_equity.values[0], color="#27ae60", alpha=0.08)
    
    ax2.set_title(f"DAIS Accumulated Capital Growth Curve — {ticker}", fontsize=11, fontweight="bold")
    ax2.set_ylabel("Portfolio Net Value ($)", fontsize=10)
    ax2.grid(True, linestyle=":", alpha=0.5)
    ax2.legend(loc="upper left", frameon=True, fontsize=9)
    
    plt.gcf().autofmt_xdate()
    plt.tight_layout()
    
    p2 = os.path.join(output_dir, f"{ticker}_equity_curve.png")
    fig.savefig(p2, bbox_inches="tight", dpi=120)
    plt.close(fig)
    chart_paths["equity_curve"] = p2

    # ------------------------------------------------------------
    # CHART 3: INTRADAY INVENTORY POSITION DENSITY
    # ------------------------------------------------------------
    fig, ax3 = plt.subplots(figsize=(11, 3), dpi=120)
    
    inventory_series = pd.Series(ledger_sorted["Inventory"].values, index=ledger_dates)
    vis_inventory = _downsample_series(inventory_series, target_points=1500)
    
    ax3.bar(vis_inventory.index, vis_inventory.values, width=max(0.001, 1.5/len(vis_inventory)), 
            color="#2980b9", alpha=0.6, label="Open Inventory Units")
    
    ax3.set_title(f"Intraday Inventory Allocation Over Time — {ticker}", fontsize=11, fontweight="bold")
    ax3.set_ylabel("Shares Retained (Qty)", fontsize=10)
    ax3.grid(True, linestyle=":", alpha=0.5)
    ax3.legend(loc="upper left", frameon=True, fontsize=9)
    
    plt.gcf().autofmt_xdate()
    plt.tight_layout()
    
    p3 = os.path.join(output_dir, f"{ticker}_inventory_density.png")
    fig.savefig(p3, bbox_inches="tight", dpi=120)
    plt.close(fig)
    chart_paths["inventory_density"] = p3

    return chart_paths
