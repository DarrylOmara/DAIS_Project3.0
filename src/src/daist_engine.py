import pandas as pd
import numpy as np
import logging

logger = logging.getLogger("DAIS_Intraday")

class DAISTradingEngine:
    """
    DAIS: Dynamic Asymmetric Inventory Strategy
    High-Frequency Intraday Production Engine
    Dollar-based position sizing: all trades in fixed dollar amounts.
    Includes a forced end-of-session flattening rule to avoid overnight inventory risk.
    Optimized via NumPy array extraction for near-instant execution.
    """
    def __init__(
        self,
        beta,
        initial_capital,
        initial_investment_amt,
        buy_amt,
        sell_amt,
        max_consecutive_buys,
        max_total_sells,
        min_remaining_inventory_pct,
        beta_buy_multiplier,
        beta_sell_multiplier,
        stop_loss_pct=None,
        take_profit_pct=None,
        dynamic_sizing=False
    ):
        self.beta = float(beta)
        self.initial_capital = float(initial_capital)
        self.initial_investment_amt = float(initial_investment_amt)
        self.buy_amt = float(buy_amt)
        self.sell_amt = float(sell_amt)
        self.max_consecutive_buys = int(max_consecutive_buys)
        self.max_total_sells = int(max_total_sells)
        self.min_remaining_inventory_pct = float(min_remaining_inventory_pct)
        self.beta_buy_multiplier = float(beta_buy_multiplier)
        self.beta_sell_multiplier = float(beta_sell_multiplier)
        self.stop_loss_pct = float(stop_loss_pct) if stop_loss_pct is not None else None
        self.take_profit_pct = float(take_profit_pct) if take_profit_pct is not None else None
        self.dynamic_sizing = bool(dynamic_sizing)

        # Reset tracking metrics
        self.cash = self.initial_capital
        self.inventory = 0                # Shares held
        self.total_cost = 0.0             # Total $ spent on current inventory
        self.average_cost = 0.0           # Average $/share of current inventory
        self.inventory_value = 0.0        # Current market value of inventory
        self.consecutive_buys = 0
        self.total_sells = 0
        self.initial_investment_cost = 0.0

        # Trade ledger: explicit record of all executed trades
        self.trades = []  # List of dicts with trade details

        # Performance trace counters
        self.sell_rule_stats = {
            "rejected_ma20": 0,
            "rejected_avg_cost": 0,
            "rejected_inventory_floor": 0,
            "executed_sells": 0,
            "overnight_liquidations": 0,
            "stop_loss_triggered": 0,
            "take_profit_triggered": 0,
        }
        self.trade_stats = {"core_buys": 0, "base_buys": 0, "buy_signals": 0, "sell_signals": 0}

    def _get_dynamic_buy_amt(self):
        """Calculate dynamic buy amount based on current cash."""
        if not self.dynamic_sizing:
            return self.buy_amt
        # Example: Invest 10% of remaining cash, but at least self.buy_amt
        return max(self.cash * 0.1, self.buy_amt)

    def _execute_buy(self, timestamp, price, buy_amt_dollars, slippage_bps, trade_type="base"):
        """
        Execute a buy order for a fixed dollar amount.
        """
        execution_price = price * (1.0 + slippage_bps)
        shares = int(buy_amt_dollars / execution_price)
        cost = shares * execution_price

        if cost <= 0 or self.cash < cost:
            return False

        self.cash -= cost
        self.inventory += shares
        self.total_cost += cost
        self.average_cost = self.total_cost / self.inventory if self.inventory > 0 else 0.0

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

        if self.initial_investment_cost <= 0 and trade_type == "core":
            self.initial_investment_cost = cost

        if trade_type == "core":
            self.trade_stats["core_buys"] += 1
        else:
            self.trade_stats["base_buys"] += 1
        self.trade_stats["buy_signals"] += 1
        self.consecutive_buys += 1
        return True

    def _execute_sell(self, timestamp, price, sell_amt_dollars, ma20, slippage_bps, force_flat=False, sell_reason="profit_taking"):
        """
        Execute a sell order for a fixed dollar amount or all inventory if force_flat.
        """
        if self.inventory <= 0:
            return False

        execution_price = price * (1.0 - slippage_bps)

        if not force_flat and sell_reason == "profit_taking":
            if execution_price < ma20:
                self.sell_rule_stats["rejected_ma20"] += 1
                return False

            if execution_price < self.average_cost:
                self.sell_rule_stats["rejected_avg_cost"] += 1
                return False

            shares_to_sell = int(sell_amt_dollars / execution_price)
            available_shares = self.inventory
            if shares_to_sell > available_shares:
                shares_to_sell = available_shares
        else:
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
        self.total_sells += 1

        if self.inventory > 0:
            self.average_cost = self.total_cost / self.inventory
        else:
            self.average_cost = 0.0
            self.total_cost = 0.0
            self.initial_investment_cost = 0.0

        self.trades.append({
            "timestamp": timestamp,
            "side": "SELL",
            "type": sell_reason,
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
        elif sell_reason == "stop_loss":
            self.sell_rule_stats["stop_loss_triggered"] += 1
        elif sell_reason == "take_profit":
            self.sell_rule_stats["take_profit_triggered"] += 1
        else:
            self.sell_rule_stats["executed_sells"] += 1

        self.trade_stats["sell_signals"] += 1
        return True

    def run_backtest(self, df, cfg):
        slippage_bps = float(cfg.get("slippage_bps", 0.0002))
        force_flat_at_close = bool(cfg.get("force_flat_at_close", True))
        buffer_min = int(cfg.get("market_close_buffer_min", 15))

        prices = df["Close"].to_numpy(dtype=np.float64)
        ma20_arr = df["MA20"].to_numpy(dtype=np.float64)
        timestamps = df.index
        time_strings = timestamps.strftime("%H:%M").to_numpy()

        ledger = []
        n_rows = len(df)

        if n_rows < 2:
            return pd.DataFrame()

        for i in range(1, n_rows):
            price = prices[i]
            ma20 = ma20_arr[i]

            # --- OVERNIGHT RISK FLATTENING ---
            if force_flat_at_close:
                hr_min = time_strings[i]
                hour, minute = int(hr_min[:2]), int(hr_min[3:])
                minutes_past_midnight = hour * 60 + minute

                if minutes_past_midnight >= (15 * 60 + (60 - buffer_min)) and self.inventory > 0:
                    self._execute_sell(timestamps[i], price, self.inventory, ma20, slippage_bps, force_flat=True, sell_reason="forced_liquidation")
                    ledger.append({
                        "Date": timestamps[i], "Price": price, "Cash": self.cash,
                        "Inventory": self.inventory, "Avg_Cost": self.average_cost, "Total_Value": self.cash + (self.inventory * price)
                    })
                    continue

            # --- RISK MANAGEMENT: STOP LOSS & TAKE PROFIT ---
            if self.inventory > 0:
                current_pnl_pct = (price / self.average_cost) - 1.0

                if self.stop_loss_pct and current_pnl_pct <= -self.stop_loss_pct:
                    logger.warning(f"STOP LOSS TRIGGERED: {current_pnl_pct:.2%} at {price}")
                    self._execute_sell(timestamps[i], price, self.inventory, ma20, slippage_bps, force_flat=True, sell_reason="stop_loss")
                elif self.take_profit_pct and current_pnl_pct >= self.take_profit_pct:
                    logger.info(f"TAKE PROFIT TRIGGERED: {current_pnl_pct:.2%} at {price}")
                    self._execute_sell(timestamps[i], price, self.inventory, ma20, slippage_bps, force_flat=True, sell_reason="take_profit")

            # --- DIRECTIONAL BUY/SELL ---
            change_pct = (price - prices[i-1]) / prices[i-1] if prices[i-1] > 0 else 0.0
            beta_threshold_buy = self.beta_buy_multiplier * self.beta
            beta_threshold_sell = self.beta_sell_multiplier * self.beta

            buy_amount = self.initial_investment_amt if self.inventory == 0 else self._get_dynamic_buy_amt()
            buy_type = "core" if self.inventory == 0 else "base"

            can_buy = (
                self.consecutive_buys < self.max_consecutive_buys and
                self.cash >= buy_amount and
                (self.inventory * price + buy_amount) <= self.initial_capital
            )

            can_sell = (self.total_sells < self.max_total_sells and self.inventory > 0)

            buy_executed = False
            sell_executed = False

            if change_pct <= beta_threshold_buy and can_buy:
                buy_executed = self._execute_buy(timestamps[i], price, buy_amount, slippage_bps, trade_type=buy_type)
            elif change_pct >= beta_threshold_sell and can_sell and self.initial_investment_cost > 0:
                remaining_value = max((self.inventory * price) - self.sell_amt, 0.0)
                min_inventory_value = self.initial_investment_cost * self.min_remaining_inventory_pct

                if remaining_value >= min_inventory_value:
                    sell_executed = self._execute_sell(timestamps[i], price, self.sell_amt, ma20, slippage_bps, force_flat=False)

            if sell_executed:
                self.consecutive_buys = 0

            ledger.append({
                "Date": timestamps[i],
                "Price": price,
                "Cash": self.cash,
                "Inventory": self.inventory,
                "Avg_Cost": self.average_cost,
                "Total_Value": self.cash + (self.inventory * price)
            })

        return pd.DataFrame(ledger)

    def get_trades_dataframe(self):
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame(self.trades)
