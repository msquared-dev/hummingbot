from decimal import Decimal
from typing import Tuple
from hummingbot.client.hummingbot_application import HummingbotApplication
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.buy_sell_loop_strategy import BuySellLoopStrategy
from hummingbot.strategy.buy_sell_loop_config_map import buy_sell_loop_config_map as c_map

def start(self):
    try:
        exchange = c_map.get("exchange").value.lower()
        trading_pair = c_map.get("market").value
        trade_amount_usdt = c_map.get("trade_amount_usdt").value
        trade_frequency = c_map.get("trade_frequency").value
        max_buy_price = c_map.get("max_buy_price").value
        min_sell_price = c_map.get("min_sell_price").value
        auto_mode = c_map.get("auto_mode").value

        market_names = [(exchange, [trading_pair])]
        self._initialize_markets(market_names)
        maker_data = [self.markets[exchange], trading_pair]
        self.market_trading_pair_tuples = [MarketTradingPairTuple(*maker_data)]

        self.strategy = BuySellLoopStrategy()
        self.strategy.init_params(
            market_info=self.market_trading_pair_tuples[0],
            trade_amount_usdt=trade_amount_usdt,
            trade_frequency=trade_frequency,
            max_buy_price=max_buy_price,
            min_sell_price=min_sell_price,
            auto_mode=auto_mode
        )
    except Exception as e:
        self.notify(str(e))
        self.logger().error("Error during initialization.", exc_info=True)
