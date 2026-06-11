import pandas as pd
import numpy as np

class DAISTradingEngine:
    """
    DAIS: Dynamic Asymmetric Inventory Strategy
    High-Frequency Intraday Production Engine
    Dollar-based position sizing: all trades in fixed dollar amounts.
    Optimized via NumPy array extraction for near-instant execution.
    """
    def __init__(self, beta, initial_capital, core_buy_amt, base_buy_amt, base_sell_amt, inventory_floor_amt):
        self.beta = float(beta)
        self.initial_capital = float(initial_capital)
        self.core_buy_amt = float(core_buy_amt)           # Dollar amount for core entry
        self.base_buy_amt = float(base_buy_amt)           # Dollar amount for incremental buys
        self.base_sell_amt = float(base_sell_amt)         # Dollar amount for profit-taking
        self.inventory_floor_amt = float(inventory_floor_amt)  # Minimum inventory value in dollars
        
        # Reset tracking metrics
        self.cash = self.initial_capital
        self.inventory = 0                # Shares held
        self.total_cost = 0.0             # Total $ spent on current inventory
        self.average_cost = 0.0           # Average $/share of current inventory
        self.inventory_value = 0.0        # Current market value of inventory
        
        # Trade ledger: explicit record of all executed trades
        self.trades = []  # List of dicts with trade details
        
        # Performance trace counters
        self.sell_rule_stats = {"rejected_ma20": 0, "rejected_avg_cost": 0, "executed_sells": 0, "overnight_liquidations": 0}
        self.trade_stats = {"core_buys": 0, "base_buys": 0}

    def _execute_buy(self, timestamp, price, buy_amt_dollars, slippage_bps, trade_type="base"):
        """
        Execute a buy order for a fixed dollar amount.
        
        Args:
            timestamp: Trade timestamp
            price: Current price per share
            buy_amt_dollars: Dollar amount to invest
            slippage_bps: Execution slippage in basis points
            trade_type: 'core' or 'base' for categorization
        
        Returns:
            bool: True if buy executed, False if insufficient cash
        """
        # Apply execution friction penalty to the entry fill price
        execution_price = price * (1.0 + slippage_bps)
        
        # Calculate shares from dollar amount
        shares = int(buy_amt_dollars / execution_price)
        cost = shares * execution_price
        
        if cost <= 0 or self.cash < cost:
            return False  # Strict liquidity protection check
        
        self.cash -= cost
        self.inventory += shares
        self.total_cost += cost
        self.average_cost = self.total_cost / self.inventory if self.inventory > 0 else 0.0
        
        # Record trade
        self.trades.append({
            "timestamp": timestamp,
            "side": "BUY",
            "type": trade_type,
            "shares": shares,
            "price_requested": price,
            "execution_price": execution_price,
            "amount_requested": buy_amt_dollars,
            "amount_executed": cost,
            "slippage_bps": slippage_bps,
            "cash_after": self.cash,
            "inventory_after": self.inventory,
            "avg_cost_after": self.average_cost,
        })
        
        if trade_type == "core":
            self.trade_stats["core_buys"] += 1
        else:
            self.trade_stats["base_buys"] += 1
        return True

    def _execute_sell(self, timestamp, price, sell_amt_dollars, ma20, slippage_bps, force_flat=False):
        """
        Execute a sell order for a fixed dollar amount or all inventory if force_flat.
        
        Args:
            timestamp: Trade timestamp
            price: Current price per share
            sell_amt_dollars: Dollar amount to sell (ignored if force_flat=True)
            ma20: MA20 trend line (for rule-based rejection)
            slippage_bps: Execution slippage in basis points
            force_flat: If True, liquidate all inventory at market
        
        Returns:
            bool: True if sell executed, False if rejected or no inventory
        """
        if self.inventory <= 0:
            return False
        
        # Apply execution friction penalty to the exit fill price
        execution_price = price * (1.0 - slippage_bps)
        
        if not force_flat:
            # HARD RULE 1: Never sell below MA20 trend line
            if execution_price < ma20:
                self.sell_rule_stats["rejected_ma20"] += 1
                return False
            
            # HARD RULE 2: Never sell below average position cost basis
            if execution_price < self.average_cost:
                self.sell_rule_stats["rejected_avg_cost"] += 1
                return False
            
            # Calculate shares to sell based on dollar amount
            shares_to_sell = int(sell_amt_dollars / execution_price)
            shares_to_sell = min(shares_to_sell, self.inventory)
        else:
            # Force flat: liquidate all inventory at market
            shares_to_sell = self.inventory
        
        if shares_to_sell <= 0:
            return False
        
        revenue = shares_to_sell * execution_price
        cost_basis = self.average_cost * shares_to_sell
        pnl = revenue - cost_basis
        pnl_pct = (pnl / cost_basis * 100.0) if cost_basis > 0 else 0.0
        
        self.cash += revenue
        self.inventory -= shares_to_sell
        self.total_cost -= self.average_cost * shares_to_sell
        
        if self.inventory > 0:
            self.average_cost = self.total_cost / self.inventory
        else:
            self.average_cost = 0.0
            self.total_cost = 0.0
        
        # Record trade
        self.trades.append({
            "timestamp": timestamp,
            "side": "SELL",
            "type": "forced_liquidation" if force_flat else "profit_taking",
            "shares": shares_to_sell,
            "price_requested": price,
            "execution_price": execution_price,
            "amount_requested": sell_amt_dollars if not force_flat else 0,
            "amount_executed": revenue,
            "cost_basis": cost_basis,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "slippage_bps": slippage_bps,
            "cash_after": self.cash,
            "inventory_after": self.inventory,
            "avg_cost_after": self.average_cost,
        })
        
        if force_flat:
            self.sell_rule_stats["overnight_liquidations"] += 1
        else:
            self.sell_rule_stats["executed_sells"] += 1
        return True

    def run_backtest(self, df, cfg):
        # Extract configuration settings
        slippage_bps = float(cfg.get("slippage_bps", 0.0002))
        force_flat_at_close = bool(cfg.get("force_flat_at_close", True))
        buffer_min = int(cfg.get("market_close_buffer_min", 15))
        
        # Extract data series columns into fast contiguous NumPy memory blocks
        prices = df["Close"].to_numpy(dtype=np.float64)
        ma20_arr = df["MA20"].to_numpy(dtype=np.float64)
        ma50_arr = df["MA50"].to_numpy(dtype=np.float64)
        timestamps = df.index
        
        # Convert timestamps to string sequences to accelerate time checking within the loop
        time_strings = timestamps.strftime("%H:%M").to_numpy()
        
        ledger = []
        n_rows = len(df)
        
        if n_rows < 2:
            return pd.DataFrame()

        # Execute high-speed array scan
        for i in range(1, n_rows):
            price = prices[i]
            ma20 = ma20_arr[i]
            ma50 = ma50_arr[i]
            
            prev_ma20 = ma20_arr[i - 1]
            prev_ma50 = ma50_arr[i - 1]
            
            # --- OVERNIGHT RISK FLATTENING SYSTEM ---
            if force_flat_at_close:
                hr_min = time_strings[i]  # Format: "15:45"
                hour, minute = int(hr_min[:2]), int(hr_min[3:])
                minutes_past_midnight = hour * 60 + minute
                
                # Check if current timestamp falls inside the session liquidation window (e.g., after 15:45)
                if minutes_past_midnight >= (15 * 60 + (60 - buffer_min)) and self.inventory > 0:
                    self._execute_sell(timestamps[i], price, self.inventory, ma20, slippage_bps, force_flat=True)
                    
                    total_value = self.cash + (self.inventory * price)
                    ledger.append({
                        "Date": timestamps[i], "Price": price, "Cash": self.cash,
                        "Inventory": self.inventory, "Avg_Cost": self.average_cost, "Total_Value": total_value
                    })
                    continue

            # --- DIRECTIONAL BUY CONDITION TRACK ---
            # Trigger macro core entry on standard bullish crossover
            if prev_ma20 < prev_ma50 and ma20 >= ma50:
                self._execute_buy(timestamps[i], price, self.core_buy_amt, slippage_bps, trade_type="core")
            
            # Trigger high-speed intraday breakout scaling
            elif price > ma20 and (self.inventory * price) >= self.inventory_floor_amt:
                scaled_buy_amt = self.base_buy_amt * self.beta
                self._execute_buy(timestamps[i], price, scaled_buy_amt, slippage_bps, trade_type="base")

            # --- DIRECTIONAL TAKE-PROFIT SELL TRACK ---
            elif price <= ma20 and (self.inventory * price) > self.inventory_floor_amt:
                scaled_sell_amt = self.base_sell_amt * self.beta
                self._execute_sell(timestamps[i], price, scaled_sell_amt, ma20, slippage_bps, force_flat=False)

            # Record high-speed historical telemetry tracking points
            total_value = self.cash + (self.inventory * price)
            ledger.append({
                "Date": timestamps[i],
                "Price": price,
                "Cash": self.cash,
                "Inventory": self.inventory,
                "Avg_Cost": self.average_cost,
                "Total_Value": total_value
            })

        return pd.DataFrame(ledger)
    
    def get_trades_dataframe(self):
        """Return all executed trades as a DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame(self.trades)
