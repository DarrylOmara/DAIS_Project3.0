"""
Safe Live-Execution Adapter Skeleton.
Framework for connecting DAIS engine output to a live broker (e.g. IBKR) with hardened risk controls.

DO NOT USE IN PRODUCTION without thorough testing, compliance review, and live paper trading.
"""
import logging
from enum import Enum
from typing import Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"

@dataclass
class Order:
    """Represents a single execution order."""
    order_id: str
    ticker: str
    qty: int
    side: str  # 'buy' or 'sell'
    limit_price: Optional[float] = None
    timestamp: Optional[datetime] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    avg_fill_price: Optional[float] = None
    
class RiskManager:
    """Enforces execution guardrails."""
    
    def __init__(
        self,
        max_single_order_notional: float = 50000,
        max_daily_loss_pct: float = 0.02,  # 2%
        max_position_size_pct: float = 0.10,  # 10% of account
        trading_hours_only: bool = True,
    ):
        self.max_single_order_notional = max_single_order_notional
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_position_size_pct = max_position_size_pct
        self.trading_hours_only = trading_hours_only
        self.daily_pnl = 0.0
        self.account_value = 100000.0
    
    def can_execute(self, order: Order, current_price: float, portfolio_value: float) -> tuple[bool, str]:
        """
        Check if order meets risk limits.
        
        Returns:
            (can_execute, reason)
        """
        # Check notional
        notional = order.qty * current_price
        if notional > self.max_single_order_notional:
            return False, f"Order notional ${notional:.2f} exceeds max ${self.max_single_order_notional:.2f}"
        
        # Check daily P&L
        if self.daily_pnl < -self.max_daily_loss_pct * portfolio_value:
            return False, f"Daily loss ${self.daily_pnl:.2f} exceeds limit"
        
        # Check trading hours (NYSE 9:30 AM - 4:00 PM ET)
        if self.trading_hours_only:
            now = datetime.now().time()
            if not (datetime.strptime("09:30", "%H:%M").time() <= now <= datetime.strptime("16:00", "%H:%M").time()):
                return False, "Outside trading hours (NYSE 9:30-16:00 ET)"
        
        return True, "OK"
    
    def record_fill(self, order: Order):
        """Record a fill for P&L tracking."""
        if order.avg_fill_price and order.filled_qty > 0:
            pnl = order.filled_qty * order.avg_fill_price if order.side == 'sell' else -order.filled_qty * order.avg_fill_price
            self.daily_pnl += pnl
            logger.info(f"Recorded fill: {order.ticker} {order.side} x{order.filled_qty} @ ${order.avg_fill_price:.2f}; daily PnL: ${self.daily_pnl:.2f}")

class BrokerAdapter:
    """Abstract broker adapter interface."""
    
    def __init__(self, account_id: str, risk_manager: Optional[RiskManager] = None):
        self.account_id = account_id
        self.risk_manager = risk_manager or RiskManager()
        self.orders: Dict[str, Order] = {}
        self.positions: Dict[str, float] = {}  # ticker -> qty
    
    def connect(self) -> bool:
        """Establish connection to broker. Override in subclass."""
        raise NotImplementedError
    
    def disconnect(self):
        """Close broker connection. Override in subclass."""
        raise NotImplementedError
    
    def get_account_value(self) -> float:
        """Get current account value. Override in subclass."""
        raise NotImplementedError
    
    def get_position(self, ticker: str) -> float:
        """Get current position size. Override in subclass."""
        return self.positions.get(ticker, 0.0)
    
    def submit_order(self, order: Order) -> bool:
        """
        Submit order with risk checks.
        
        Returns:
            True if order accepted, False if rejected.
        """
        # Risk check
        current_price = self._get_bid_ask(order.ticker)[1]  # Use ask for buys, bid for sells
        portfolio_value = self.get_account_value()
        can_execute, reason = self.risk_manager.can_execute(order, current_price, portfolio_value)
        
        if not can_execute:
            logger.warning(f"Order rejected: {reason}")
            order.status = OrderStatus.REJECTED
            return False
        
        # Submit
        logger.info(f"Submitting {order.side} order: {order.ticker} x{order.qty}")
        self.orders[order.order_id] = order
        
        # Call broker-specific implementation
        return self._submit_order_impl(order)
    
    def _submit_order_impl(self, order: Order) -> bool:
        """Broker-specific order submission. Override in subclass."""
        raise NotImplementedError
    
    def _get_bid_ask(self, ticker: str) -> tuple[float, float]:
        """Get current bid/ask. Override in subclass."""
        raise NotImplementedError
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order. Override in subclass."""
        raise NotImplementedError
    
    def get_order_status(self, order_id: str) -> OrderStatus:
        """Poll order status. Override in subclass."""
        raise NotImplementedError

class IBKRAdapter(BrokerAdapter):
    """Interactive Brokers adapter (skeleton)."""
    
    def __init__(self, account_id: str, risk_manager: Optional[RiskManager] = None):
        super().__init__(account_id, risk_manager)
        self.ib = None  # ib_insync.IB instance
    
    def connect(self) -> bool:
        """Connect to IBKR TWS/Gateway."""
        try:
            from ib_insync import IB, util
            self.ib = IB()
            self.ib.connect('127.0.0.1', 7497, clientId=1)  # TWS default
            logger.info("Connected to IBKR")
            return True
        except Exception as e:
            logger.error(f"IBKR connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from IBKR."""
        if self.ib:
            self.ib.disconnect()
            logger.info("Disconnected from IBKR")
    
    def get_account_value(self) -> float:
        """Fetch account value from IBKR."""
        if not self.ib:
            return 0.0
        try:
            # Pseudo-code; actual IBKR API call needed
            account = self.ib.managedAccounts()[0]
            summary = self.ib.accountSummary(account)
            # Extract net liquidation value
            return 100000.0  # Placeholder
        except Exception as e:
            logger.error(f"Failed to fetch account value: {e}")
            return 0.0
    
    def _submit_order_impl(self, order: Order) -> bool:
        """Submit order to IBKR."""
        if not self.ib:
            logger.error("Not connected to IBKR")
            return False
        
        try:
            from ib_insync import Stock, MarketOrder, LimitOrder
            
            contract = Stock(order.ticker, 'SMART', 'USD')
            
            if order.limit_price:
                ib_order = LimitOrder(order.side.upper(), order.qty, order.limit_price)
            else:
                ib_order = MarketOrder(order.side.upper(), order.qty)
            
            # Submit
            trade = self.ib.placeOrder(contract, ib_order)
            order.order_id = str(trade.orderId)
            order.status = OrderStatus.PENDING
            logger.info(f"Order placed: {order.order_id}")
            return True
            
        except Exception as e:
            logger.error(f"Order submission failed: {e}")
            order.status = OrderStatus.ERROR
            return False
    
    def _get_bid_ask(self, ticker: str) -> tuple[float, float]:
        """Get bid/ask for ticker."""
        if not self.ib:
            return (0.0, 0.0)
        try:
            from ib_insync import Stock
            contract = Stock(ticker, 'SMART', 'USD')
            ticker_data = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(0.5)
            return (ticker_data.bid, ticker_data.ask)
        except Exception as e:
            logger.error(f"Failed to fetch bid/ask: {e}")
            return (0.0, 0.0)

def execute_ledger(
    ledger_df,
    broker: BrokerAdapter,
    account_id: str,
    dry_run: bool = True,
):
    """
    Execute a backtest ledger on a live broker.
    
    Args:
        ledger_df: DataFrame with trade records (ticker, side, qty, price)
        broker: connected BrokerAdapter instance
        account_id: IBKR account identifier
        dry_run: if True, log orders without submitting
    
    Returns:
        List of Order objects
    """
    executed_orders = []
    
    for idx, row in ledger_df.iterrows():
        order = Order(
            order_id=f"{account_id}_{idx}",
            ticker=row['ticker'],
            qty=int(row['qty']),
            side=row['side'],
            limit_price=row.get('limit_price'),
            timestamp=datetime.now(),
        )
        
        if dry_run:
            logger.info(f"[DRY RUN] Would submit: {order}")
        else:
            broker.submit_order(order)
        
        executed_orders.append(order)
    
    return executed_orders

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Example
    risk_mgr = RiskManager(max_single_order_notional=50000, max_daily_loss_pct=0.02)
    broker = IBKRAdapter("U123456", risk_manager=risk_mgr)
    
    # Dry run: don't actually connect
    order = Order(order_id="TEST_001", ticker="MSFT", qty=100, side="buy", limit_price=300.0)
    can_exec, reason = risk_mgr.can_execute(order, 300.0, 100000.0)
    print(f"Risk check: {can_exec} ({reason})")
