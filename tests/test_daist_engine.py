import unittest
import pandas as pd
from src.src.daist_engine import DAISTradingEngine


class TestDAISTradingEngine(unittest.TestCase):
    def test_run_backtest_respects_beta_sell_inventory_floor(self):
        # Construct a simple intraday series that triggers an initial buy,
        # then a large reversal where a fixed-dollar sell would breach the inventory floor.
        timestamps = pd.date_range("2025-01-02 09:30", periods=3, freq="5min")
        df = pd.DataFrame(
            {
                "Close": [1.00, 0.40, 1.40],
                "MA20": [0.90, 0.35, 1.10],
                "MA50": [0.95, 0.38, 1.15],
            },
            index=timestamps,
        )

        engine = DAISTradingEngine(
            beta=1.0,
            initial_capital=1000.0,
            initial_investment_amt=1.0,
            buy_amt=1.0,
            sell_amt=20.0,
            max_consecutive_buys=4,
            max_total_sells=3,
            min_remaining_inventory_pct=0.40,
            beta_buy_multiplier=-0.5,
            beta_sell_multiplier=2.0,
        )

        ledger = engine.run_backtest(
            df,
            cfg={"slippage_bps": 0.0000, "force_flat_at_close": False, "market_close_buffer_min": 15},
        )

        # The first signal should buy into the position using a core buy.
        self.assertEqual(len(engine.trades), 1)
        self.assertEqual(engine.trades[0]["side"], "BUY")
        self.assertEqual(engine.trades[0]["type"], "core")
        self.assertEqual(engine.trade_stats["core_buys"], 1)
        self.assertEqual(engine.trade_stats["sell_signals"], 0)

        # Because the next sell signal would violate the minimum remaining inventory floor,
        # the engine should not execute a sell and should preserve the position.
        self.assertGreater(engine.inventory, 0)
        self.assertLess(engine.cash, engine.initial_capital)
        self.assertEqual(engine.sell_rule_stats["executed_sells"], 0)

        # The backtest ledger should still record portfolio snapshots.
        self.assertFalse(ledger.empty)
        self.assertEqual(ledger.iloc[-1]["Inventory"], engine.inventory)

    def test_run_backtest_respects_max_consecutive_buys(self):
        # Construct a series with repeated strong down bars to trigger multiple buy signals.
        timestamps = pd.date_range("2025-01-02 09:30", periods=6, freq="5min")
        df = pd.DataFrame(
            {
                "Close": [1.00, 0.40, 0.16, 0.064, 0.0256, 0.01024],
                "MA20": [0.90, 0.35, 0.15, 0.06, 0.02, 0.01],
                "MA50": [0.95, 0.38, 0.16, 0.07, 0.03, 0.01],
            },
            index=timestamps,
        )

        engine = DAISTradingEngine(
            beta=1.0,
            initial_capital=1000.0,
            initial_investment_amt=100.0,
            buy_amt=10.0,
            sell_amt=20.0,
            max_consecutive_buys=4,
            max_total_sells=3,
            min_remaining_inventory_pct=0.40,
            beta_buy_multiplier=-0.5,
            beta_sell_multiplier=2.0,
        )

        engine.run_backtest(
            df,
            cfg={"slippage_bps": 0.0, "force_flat_at_close": False, "market_close_buffer_min": 15},
        )

        # The engine should execute exactly the configured max consecutive buys and then pause.
        self.assertEqual(engine.trade_stats["buy_signals"], 4)
        self.assertEqual(engine.trade_stats["core_buys"] + engine.trade_stats["base_buys"], 4)
        self.assertEqual(engine.consecutive_buys, 4)
        self.assertEqual(len(engine.trades), 4)

    def test_run_backtest_forces_flat_sell_at_close(self):
        timestamps = pd.to_datetime([
            "2025-01-02 09:30",
            "2025-01-02 09:35",
            "2025-01-02 15:50",
        ])
        df = pd.DataFrame(
            {
                "Close": [1.00, 0.40, 1.00],
                "MA20": [0.90, 0.35, 0.95],
                "MA50": [0.95, 0.38, 0.98],
            },
            index=timestamps,
        )

        engine = DAISTradingEngine(
            beta=1.0,
            initial_capital=1000.0,
            initial_investment_amt=1.0,
            buy_amt=1.0,
            sell_amt=20.0,
            max_consecutive_buys=4,
            max_total_sells=3,
            min_remaining_inventory_pct=0.40,
            beta_buy_multiplier=-0.5,
            beta_sell_multiplier=2.0,
        )

        ledger = engine.run_backtest(
            df,
            cfg={"slippage_bps": 0.0, "force_flat_at_close": True, "market_close_buffer_min": 15},
        )

        self.assertEqual(engine.inventory, 0)
        self.assertEqual(engine.sell_rule_stats["overnight_liquidations"], 1)
        self.assertEqual(engine.trade_stats["sell_signals"], 1)
        self.assertEqual(engine.trades[-1]["type"], "forced_liquidation")
        self.assertEqual(ledger.iloc[-1]["Inventory"], 0)


if __name__ == "__main__":
    unittest.main()
