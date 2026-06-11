**DAIS Intraday Backtest — Overview**

DAIS is a lightweight intraday research and backtesting pipeline that downloads price series, runs a simulated execution engine, produces analytics, and exports multi-format deliverables for stakeholder reporting.

**Quick Start**
- **Install dependencies:**

```bash
python -m pip install -r requirements.txt
```

- **Run the pipeline:**

```bash
python run_all.py
```

**Configuration**
- `config.yaml` controls the run. Key entries:
  - `tickers`: list of tickers to process.
  - `benchmark`: benchmark ticker (set to `^IXIC` for NASDAQ composite).
  - `bar_interval`: intraday bar size (e.g. `1m`, `5m`, `15m`).
  - `lookback_days`: days to fetch for daily series.
  - `intraday_lookback_days`: (optional) days to fetch for intraday bars.
  
  **Trading Parameters (Dollar-Based Position Sizing)**
  - `initial_capital`: starting trading capital (e.g. $10,000).
  - `core_buy_amt`: fixed dollar amount for macro directional entry (e.g. $500).
  - `base_buy_amt`: fixed dollar amount for incremental buys per signal (e.g. $250).
  - `base_sell_amt`: fixed dollar amount for profit-taking per signal (e.g. $250).
  - `inventory_floor_amt`: minimum position value in dollars before allowing more buys (e.g. $100).
  - `beta_default`: scaling factor for buy/sell amounts (1.0 = no scaling, >1.0 = scaled up).
  - `slippage_bps`: expected execution slippage in basis points (e.g. 0.0002 = 0.02%).
  - `short_window`: fast EMA window (e.g. 9 bars).
  - `long_window`: slow EMA window (e.g. 21 bars).
  - `force_flat_at_close`: liquidate all positions before market close (true/false).
  - `market_close_buffer_min`: minutes before close to start liquidation (e.g. 15 min).
  
  - `data_dir`: folder for cached CSV files.
  - `output_dir`: folder for generated deliverables.

**What it does (high level)**
- Downloads intraday (preferred) or daily data for each ticker and caches to `data/{TICKER}.csv`.
- Computes indicators (moving averages) and aligns timestamps to the benchmark.
- Runs the `DAISTradingEngine` backtest using fixed dollar amounts for all entry/exit trades to produce a ledger of trades and P&L.
- Produces metrics, charts, and documentation: PDF, PPTX, interactive HTML dashboard, and DOCX manual placed in `outputs/DAIS_Deliverables`.

**Trading Logic (Dollar-Based)**
- **Core Entry**: On MA20 > MA50 crossover, buy `core_buy_amt` dollars of the stock.
- **Incremental Buys**: If price > MA20 and position value ≥ `inventory_floor_amt`, buy `base_buy_amt * beta` dollars.
- **Profit Taking**: If price ≤ MA20 and position value > `inventory_floor_amt`, sell `base_sell_amt * beta` dollars.
- **Hard Rules**: Never sell below MA20 (trend protection) or below average cost basis (no loss-taking).
- **Session Close**: Liquidate all remaining positions `market_close_buffer_min` before market close.

**Extending & Next Steps**
- Use a paid intraday data provider (higher fidelity) by replacing `fetch_intraday()` in [src/src/data_fetcher.py](src/src/data_fetcher.py).
- Add a live broker adapter (e.g. IBKR) behind a hardened risk layer to move from backtest → execution. See [src/src/ibkr_adapter_skeleton.py](src/src/ibkr_adapter_skeleton.py) for a starting point.
- Add a parameter sweep harness to test many combinations (grid/random search) and persist results in `outputs/`.
- Add unit and integration tests (see `tests/` skeleton added here). Use `pytest` for fast feedback.
- Add CI to run tests on push (GitHub Actions workflow included).

**Caveats**
- yfinance intraday data has lookback and accuracy limits — not suitable as a production market data feed for live execution.
- Backtest results depend on assumptions about slippage and fills; validate with higher-fidelity data before any live deployment.

**Files of interest**
- `run_all.py` — pipeline orchestrator.
- `src/src/data_fetcher.py` — data download/CSV handling (intraday + daily).
- `src/src/daist_engine.py` — execution/backtest engine.
- `config.yaml` — runtime configuration.

If you want, I can also: add a parameter-sweep runner, wire a paid intraday feed adapter, or scaffold a safe live-execution adapter. Tell me which to prioritize.
# DAIS Project

Dynamic Asymmetric Inventory‑Aware Strategy (DAIS)

## How to run on Windows

1. Open PowerShell as Administrator  
2. Navigate to the project folder:  
   `cd C:\DAIS_Project`
3. Create virtual environment:  
   `python -m venv .venv`
4. Activate it:  
   `.\.venv\Scripts\Activate.ps1`
5. Install dependencies:  
   `pip install -r requirements.txt`
6. Run the pipeline:  
   `python run_all.py`

Outputs will appear in:

