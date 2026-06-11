from ib_insync import IB, Stock, MarketOrder, MarketOnOpenOrder
import logging

logger = logging.getLogger(__name__)

class IBKRAdapter:
    """
    Safe skeleton for IBKR integration.
    Does NOT auto-trade. Requires manual configuration.
    """

    def __init__(self, host='127.0.0.1', port=7497, clientId=1):
        self.ib = IB()
        self.host = host
        self.port = port
        self.clientId = clientId
        self.connected = False

    def connect(self):
        try:
            self.ib.connect(self.host, self.port, clientId=self.clientId)
            self.connected = True
            logger.info("Connected to IBKR")
        except Exception as e:
            logger.exception("IBKR connection failed: %s", e)
            self.connected = False

    def disconnect(self):
        if self.connected:
            self.ib.disconnect()
            self.connected = False

    def place_market_buy(self, symbol, qty):
        contract = Stock(symbol, 'SMART', 'USD')
        order = MarketOrder('BUY', qty)
        trade = self.ib.placeOrder(contract, order)
        return trade

    def place_market_on_open_sell(self, symbol, qty):
        contract = Stock(symbol, 'SMART', 'USD')
        order = MarketOnOpenOrder('SELL', qty)
        trade = self.ib.placeOrder(contract, order)
        return trade
