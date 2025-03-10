from decimal import Decimal
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.ping_pong import PingPong
from hummingbot.strategy.ping_pong.ping_pong_config_map import ping_pong_config_map as c_map

def start(self):
    # Получаем значения из конфигурационной карты
    connector = c_map.get("connector").value.lower()
    market = c_map.get("market").value

    # Инициализация маркетов
    self._initialize_markets([(connector, [market])])
    base, quote = market.split("-")
    market_info = MarketTradingPairTuple(self.markets[connector], market, base, quote)
    self.market_trading_pair_tuples = [market_info]

    # Чтение параметров стратегии из конфигурации
    order_amount = Decimal(c_map.get("order_amount").value)
    time_after_buys = int(c_map.get("time_after_buys").value)
    time_after_sells = int(c_map.get("time_after_sells").value)
    rounds = int(c_map.get("rounds").value)
    count_buy_order_in_cycle = int(c_map.get("count_buy_order_in_cycle").value)
    count_sell_order_in_cycle = int(c_map.get("count_sell_order_in_cycle").value)
    min_sell_price = Decimal(c_map.get("min_sell_price").value)
    max_buy_price = Decimal(c_map.get("max_buy_price").value)
    time_between_trades = int(c_map.get("time_between_trades").value)

    # Создание и запуск стратегии с новыми параметрами
    self.strategy = PingPong(
        market_info=market_info,
        order_amount=order_amount,
        time_after_buys=time_after_buys,
        time_after_sells=time_after_sells,
        rounds=rounds,
        count_buy_order_in_cycle=count_buy_order_in_cycle,
        count_sell_order_in_cycle=count_sell_order_in_cycle,
        min_sell_price=min_sell_price,
        max_buy_price=max_buy_price,
        time_between_trades=time_between_trades
    )