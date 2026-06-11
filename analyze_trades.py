"""
Trade Analysis Utility: Quick exploration of trade execution reports.
Run this to analyze and summarize trades from the pipeline output.
"""
import os
import sys
import pandas as pd
from pathlib import Path

def analyze_trades(ticker: str, trades_dir: str = "outputs/DAIS_Deliverables"):
    """Analyze and display trade summary for a ticker."""
    
    ticker_dir = os.path.join(trades_dir, ticker)
    trades_csv = os.path.join(ticker_dir, f"{ticker}_trades.csv")
    summary_csv = os.path.join(ticker_dir, f"{ticker}_trade_summary.csv")
    
    if not os.path.exists(trades_csv):
        print(f"No trade file found for {ticker}")
        return
    
    print(f"\n{'='*80}")
    print(f"TRADE EXECUTION ANALYSIS: {ticker}")
    print(f"{'='*80}\n")
    
    # Load trades
    trades = pd.read_csv(trades_csv)
    print(f"Total Trades Executed: {len(trades)}")
    print(f"\nFirst 5 Trades:")
    print(trades[['Trade_ID', 'timestamp', 'side', 'shares', 'execution_price', 'amount_executed']].head())
    
    # Show buys
    buys = trades[trades['side'] == 'BUY']
    print(f"\nBUY TRADES: {len(buys)}")
    if len(buys) > 0:
        print(f"  Total Shares Bought: {buys['shares'].sum():.0f}")
        print(f"  Total Capital Deployed: ${buys['amount_executed'].sum():,.2f}")
        print(f"  Avg Execution Price: ${buys['execution_price'].mean():,.2f}")
    
    # Show sells
    sells = trades[trades['side'] == 'SELL']
    print(f"\nSELL TRADES: {len(sells)}")
    if len(sells) > 0:
        print(f"  Total Shares Sold: {sells['shares'].sum():.0f}")
        print(f"  Total Revenue: ${sells['amount_executed'].sum():,.2f}")
        print(f"  Avg Execution Price: ${sells['execution_price'].mean():,.2f}")
        
        # P&L for sells (if available)
        if 'pnl' in sells.columns:
            total_pnl = sells['pnl'].sum()
            winning_sells = len(sells[sells['pnl'] > 0])
            losing_sells = len(sells[sells['pnl'] < 0])
            win_rate = (winning_sells / len(sells) * 100) if len(sells) > 0 else 0
            
            print(f"\n  P&L ANALYSIS:")
            print(f"    Total P&L: ${total_pnl:,.2f}")
            print(f"    Winning Sells: {winning_sells}")
            print(f"    Losing Sells: {losing_sells}")
            print(f"    Win Rate: {win_rate:.1f}%")
    
    # Load summary
    if os.path.exists(summary_csv):
        summary = pd.read_csv(summary_csv).iloc[0].to_dict()
        print(f"\nTRADE SUMMARY STATISTICS:")
        print(f"  Total Capital Deployed: ${summary.get('total_capital_deployed', 0):,.2f}")
        print(f"  Total P&L: ${summary.get('total_pnl', 0):,.2f}")
        print(f"  Avg P&L per Sell: ${summary.get('avg_pnl_per_sell', 0):,.2f}")
    
    print(f"\n{'='*80}\n")

def list_all_trades(trades_dir: str = "outputs/DAIS_Deliverables"):
    """List all available trade reports."""
    if not os.path.exists(trades_dir):
        print(f"Directory not found: {trades_dir}")
        return []
    
    tickers = [d for d in os.listdir(trades_dir) 
               if os.path.isdir(os.path.join(trades_dir, d)) 
               and os.path.exists(os.path.join(trades_dir, d, f"{d}_trades.csv"))]
    return tickers

if __name__ == "__main__":
    # List available tickers
    tickers = list_all_trades()
    
    if not tickers:
        print("No trade reports found in outputs/DAIS_Deliverables/")
        sys.exit(0)
    
    print(f"Available trade reports: {', '.join(tickers)}\n")
    
    # Analyze all tickers or specified ticker
    if len(sys.argv) > 1:
        ticker = sys.argv[1].upper()
        if ticker in tickers:
            analyze_trades(ticker)
        else:
            print(f"Ticker {ticker} not found. Available: {', '.join(tickers)}")
    else:
        # Analyze all
        for ticker in tickers:
            analyze_trades(ticker)
