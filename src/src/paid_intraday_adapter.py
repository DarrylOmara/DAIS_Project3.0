"""
Paid Intraday Data Provider Adapter Template.
Provides a skeleton to integrate premium intraday feeds (Polygon, AlphaVantage, IQFeed, etc).

Usage:
  1. Replace API_KEY with your provider credentials
  2. Implement fetch_intraday_premium() with your provider's SDK/API
  3. Call from run_all.py in place of (or alongside) yfinance fetch_intraday()
"""
import os
import logging
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Placeholder for provider API key (store in env var or config)
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")

def fetch_intraday_premium(
    ticker: str,
    interval: str = "1m",
    period_days: int = 7,
    provider: str = "polygon",
    data_dir: str = "data"
):
    """
    Fetch intraday data from a premium provider.
    
    Args:
        ticker: symbol (e.g. 'MSFT')
        interval: bar interval (e.g. '1m', '5m', '15m')
        period_days: lookback period in days
        provider: 'polygon', 'alphavantage', 'iqfeed', etc
        data_dir: output directory for CSV
    
    Returns:
        DataFrame with OHLCV columns indexed by timestamp
    
    Raises:
        NotImplementedError if provider not yet integrated
        ValueError if API key missing
    """
    
    if provider.lower() == "polygon":
        return _fetch_polygon(ticker, interval, period_days, data_dir)
    elif provider.lower() == "alphavantage":
        return _fetch_alphavantage(ticker, interval, period_days, data_dir)
    elif provider.lower() == "iqfeed":
        return _fetch_iqfeed(ticker, interval, period_days, data_dir)
    else:
        raise NotImplementedError(f"Provider '{provider}' not yet implemented")

def _fetch_polygon(ticker: str, interval: str, period_days: int, data_dir: str):
    """Polygon.io intraday fetcher (https://polygon.io)"""
    if not POLYGON_API_KEY:
        raise ValueError("POLYGON_API_KEY env var not set")
    
    # Example using polygon-python SDK (install: pip install polygon-python-client)
    try:
        from polygon import RESTClient
    except ImportError:
        raise ImportError("Install polygon-python-client: pip install polygon-python-client")
    
    client = RESTClient(api_key=POLYGON_API_KEY)
    
    # Map interval format
    interval_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60"}
    poly_interval = interval_map.get(interval, interval)
    
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=period_days)
    
    try:
        aggs = client.get_aggs(
            ticker=ticker,
            multiplier=int(poly_interval),
            timespan="minute",
            from_=start_date.isoformat(),
            to=end_date.isoformat(),
        )
        
        if not aggs or len(aggs) == 0:
            raise ValueError(f"No data from Polygon for {ticker}")
        
        data = [{
            'datetime': pd.to_datetime(bar.timestamp, unit='ms'),
            'Open': bar.open,
            'High': bar.high,
            'Low': bar.low,
            'Close': bar.close,
            'Volume': bar.volume,
        } for bar in aggs]
        
        df = pd.DataFrame(data).set_index('datetime').sort_index()
        
        # Save
        os.makedirs(data_dir, exist_ok=True)
        df.to_csv(os.path.join(data_dir, f"{ticker}.csv"))
        
        logger.info(f"Polygon: fetched {len(df)} bars for {ticker}")
        return df
        
    except Exception as e:
        logger.error(f"Polygon fetch failed: {e}")
        raise

def _fetch_alphavantage(ticker: str, interval: str, period_days: int, data_dir: str):
    """AlphaVantage intraday fetcher (https://www.alphavantage.co)"""
    if not ALPHAVANTAGE_API_KEY:
        raise ValueError("ALPHAVANTAGE_API_KEY env var not set")
    
    # Example using Alpha Vantage SDK (install: pip install alpha_vantage)
    try:
        from alpha_vantage.timeseries import TimeSeries
    except ImportError:
        raise ImportError("Install alpha_vantage: pip install alpha_vantage")
    
    ts = TimeSeries(key=ALPHAVANTAGE_API_KEY, output_format='pandas')
    
    # AlphaVantage interval format: '1min', '5min', '15min', '60min'
    av_interval = f"{interval.replace('m', 'min')}"
    
    try:
        df, meta = ts.get_intraday(symbol=ticker, interval=av_interval)
        
        if df.empty:
            raise ValueError(f"No data from AlphaVantage for {ticker}")
        
        # Rename columns
        df.rename(columns={
            '1. open': 'Open',
            '2. high': 'High',
            '3. low': 'Low',
            '4. close': 'Close',
            '5. volume': 'Volume',
        }, inplace=True)
        
        df.index = pd.to_datetime(df.index)
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].sort_index()
        
        # Save
        os.makedirs(data_dir, exist_ok=True)
        df.to_csv(os.path.join(data_dir, f"{ticker}.csv"))
        
        logger.info(f"AlphaVantage: fetched {len(df)} bars for {ticker}")
        return df
        
    except Exception as e:
        logger.error(f"AlphaVantage fetch failed: {e}")
        raise

def _fetch_iqfeed(ticker: str, interval: str, period_days: int, data_dir: str):
    """IQFeed local socket adapter (https://www.iqfeed.net)"""
    try:
        from localconfig import passwords
    except ImportError:
        raise ImportError("IQFeed localconfig not found; requires local IQFeed installation")
    
    # Pseudo-code; real implementation requires IQFeed socket protocol
    logger.warning("IQFeed adapter not fully implemented; placeholder only")
    raise NotImplementedError("IQFeed adapter requires local installation + socket protocol")

if __name__ == "__main__":
    # Example: fetch Polygon data
    logging.basicConfig(level=logging.INFO)
    
    try:
        df = fetch_intraday_premium("MSFT", interval="5m", period_days=7, provider="polygon")
        print(f"Success: {len(df)} rows")
        print(df.head())
    except Exception as e:
        print(f"Error: {e}")
