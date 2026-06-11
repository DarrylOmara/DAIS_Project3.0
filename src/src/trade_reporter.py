"""
Trade Reporter: Comprehensive trade execution tracking and analysis.
Exports detailed trade records with P&L, execution details, and summary statistics.
"""
import os
import logging
from datetime import datetime
import pandas as pd
import numpy as np

logger = logging.getLogger("DAIS_Intraday.TradeReporter")

def generate_trade_report(ticker: str, trades_df: pd.DataFrame, outdir: str) -> str:
    """
    Generate a detailed trade report CSV with all execution details.
    
    Args:
        ticker: Ticker symbol
        trades_df: DataFrame from engine.get_trades_dataframe()
        outdir: Output directory
    
    Returns:
        Path to generated trade report CSV
    """
    if trades_df.empty:
        logger.warning(f"No trades executed for {ticker}")
        return None
    
    # Ensure output directory exists
    os.makedirs(outdir, exist_ok=True)
    
    # Add trade number
    trades_df = trades_df.copy()
    trades_df.insert(0, "Trade_ID", range(1, len(trades_df) + 1))
    
    # Format timestamp
    trades_df["timestamp"] = pd.to_datetime(trades_df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")
    
    # Reorder columns for better readability
    col_order = [
        "Trade_ID", "timestamp", "side", "type", "shares", 
        "price_requested", "execution_price", 
        "amount_requested", "amount_executed"
    ]
    
    # Add P&L columns for sells only
    if "pnl" in trades_df.columns:
        col_order.extend(["cost_basis", "pnl", "pnl_pct"])
    
    col_order.extend([
        "slippage_bps", "cash_after", "inventory_after", "avg_cost_after"
    ])
    
    # Keep only available columns
    col_order = [c for c in col_order if c in trades_df.columns]
    trades_df = trades_df[col_order]
    
    # Save to CSV (keep numeric format for analysis)
    trades_csv = os.path.join(outdir, f"{ticker}_trades.csv")
    trades_df.to_csv(trades_csv, index=False)
    logger.info(f"Trade report generated: {trades_csv}")
    
    return trades_csv

def generate_trade_summary(ticker: str, trades_df: pd.DataFrame, outdir: str) -> dict:
    """
    Generate trade execution summary statistics.
    
    Args:
        ticker: Ticker symbol
        trades_df: DataFrame from engine.get_trades_dataframe()
        outdir: Output directory
    
    Returns:
        Dictionary with summary statistics
    """
    if trades_df.empty:
        return {
            "ticker": ticker,
            "total_trades": 0,
            "buy_trades": 0,
            "sell_trades": 0,
            "total_shares_bought": 0,
            "total_shares_sold": 0,
            "total_capital_deployed": 0.0,
            "total_pnl": 0.0,
            "profitable_sells": 0,
            "losing_sells": 0,
            "avg_pnl_per_sell": 0.0,
            "win_rate": 0.0,
        }
    
    # Trade counts
    buy_trades = trades_df[trades_df["side"] == "BUY"]
    sell_trades = trades_df[trades_df["side"] == "SELL"]
    
    total_trades = len(trades_df)
    total_buys = len(buy_trades)
    total_sells = len(sell_trades)
    
    # Share statistics
    total_shares_bought = buy_trades["shares"].sum() if len(buy_trades) > 0 else 0
    total_shares_sold = sell_trades["shares"].sum() if len(sell_trades) > 0 else 0
    
    # Capital deployed
    total_capital_deployed = buy_trades["amount_executed"].sum() if len(buy_trades) > 0 else 0.0
    
    # P&L analysis (for sell trades)
    if len(sell_trades) > 0 and "pnl" in sell_trades.columns:
        total_pnl = sell_trades["pnl"].sum()
        profitable_sells = len(sell_trades[sell_trades["pnl"] > 0])
        losing_sells = len(sell_trades[sell_trades["pnl"] < 0])
        avg_pnl_per_sell = total_pnl / total_sells if total_sells > 0 else 0.0
        win_rate = (profitable_sells / total_sells * 100.0) if total_sells > 0 else 0.0
    else:
        total_pnl = 0.0
        profitable_sells = 0
        losing_sells = 0
        avg_pnl_per_sell = 0.0
        win_rate = 0.0
    
    summary = {
        "ticker": ticker,
        "total_trades": total_trades,
        "buy_trades": total_buys,
        "sell_trades": total_sells,
        "total_shares_bought": total_shares_bought,
        "total_shares_sold": total_shares_sold,
        "total_capital_deployed": total_capital_deployed,
        "total_pnl": total_pnl,
        "profitable_sells": profitable_sells,
        "losing_sells": losing_sells,
        "avg_pnl_per_sell": avg_pnl_per_sell,
        "win_rate": win_rate,
    }
    
    # Save summary to CSV
    summary_csv = os.path.join(outdir, f"{ticker}_trade_summary.csv")
    pd.DataFrame([summary]).to_csv(summary_csv, index=False)
    logger.info(f"Trade summary generated: {summary_csv}")
    
    return summary

def format_trade_summary_for_display(summary: dict) -> str:
    """
    Format trade summary for console/report display.
    
    Args:
        summary: Dictionary from generate_trade_summary()
    
    Returns:
        Formatted string for display
    """
    lines = []
    lines.append(f"\n{'='*70}")
    lines.append(f"TRADE EXECUTION SUMMARY: {summary['ticker']}")
    lines.append(f"{'='*70}")
    lines.append(f"Total Trades:              {summary['total_trades']:>6}")
    lines.append(f"  Buy Trades:              {summary['buy_trades']:>6}")
    lines.append(f"  Sell Trades:             {summary['sell_trades']:>6}")
    lines.append(f"")
    lines.append(f"Volume Traded:")
    lines.append(f"  Total Shares Bought:     {summary['total_shares_bought']:>6.0f}")
    lines.append(f"  Total Shares Sold:       {summary['total_shares_sold']:>6.0f}")
    lines.append(f"  Capital Deployed:        ${summary['total_capital_deployed']:>14,.2f}")
    lines.append(f"")
    lines.append(f"Profitability:")
    lines.append(f"  Total P&L:               ${summary['total_pnl']:>14,.2f}")
    lines.append(f"  Profitable Sells:        {summary['profitable_sells']:>6.0f}")
    lines.append(f"  Losing Sells:            {summary['losing_sells']:>6.0f}")
    lines.append(f"  Win Rate:                {summary['win_rate']:>13.1f}%")
    lines.append(f"  Avg P&L per Sell:        ${summary['avg_pnl_per_sell']:>14,.2f}")
    lines.append(f"{'='*70}\n")
    
    return "\n".join(lines)

if __name__ == "__main__":
    # Example usage
    import sys
    logging.basicConfig(level=logging.INFO)
