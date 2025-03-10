#!/usr/bin/env python

import logging
from decimal import Decimal

from hummingbot.core.event.events import OrderType
from hummingbot.logger import HummingbotLogger
from hummingbot.strategy.market_trading_pair_tuple import MarketTradingPairTuple
from hummingbot.strategy.strategy_py_base import StrategyPyBase

logger_instance = None


class PingPong(StrategyPyBase):
    """
    Стратегия выполняет следующие этапы:
      1. Выполняет n рыночных ордеров на покупку (если текущая цена <= max_buy_price), с задержкой между ордерами.
      2. Ждет time_after_buys секунд после завершения покупок.
      3. Выполняет m рыночных ордеров на продажу (если текущая цена >= min_sell_price), с задержкой между ордерами.
      4. Ждет time_after_sells секунд после завершения продаж.
      5. Повторяет цикл заданное число раз или бесконечно (если rounds = -1).
    """

    @classmethod
    def logger(cls) -> HummingbotLogger:
        global logger_instance
        if logger_instance is None:
            logger_instance = logging.getLogger(__name__)
        return logger_instance

    def __init__(self,
                 market_info: MarketTradingPairTuple,
                 order_amount: Decimal,
                 time_after_buys: int,
                 time_after_sells: int,
                 rounds: int,
                 count_buy_order_in_cycle: int,
                 count_sell_order_in_cycle: int,
                 min_sell_price: Decimal,
                 max_buy_price: Decimal,
                 time_between_trades: int):
        """
        Параметры:
          - market_info: кортеж с информацией о рынке и торговой паре.
          - order_amount: объём ордера (одинаковый для покупок и продаж).
          - time_after_buys: задержка после покупок (t) в секундах.
          - time_after_sells: задержка после продаж (c) в секундах.
          - rounds: количество циклов; если rounds = -1, то цикл выполняется бесконечно.
          - count_buy_order_in_cycle: количество ордеров на покупку (n).
          - count_sell_order_in_cycle: количество ордеров на продажу (m).
          - min_sell_price: минимальная цена для продажи (если текущая цена ниже – продажа не происходит).
          - max_buy_price: максимальная цена для покупки (если текущая цена выше – покупка не происходит).
          - time_between_trades: задержка между отдельными ордерами в рамках одного цикла.
        """
        super().__init__()
        self._market_info = market_info
        self.add_markets([market_info.market])
        self._order_amount = order_amount
        self._time_after_buys = time_after_buys
        self._time_after_sells = time_after_sells
        self._total_rounds = rounds
        self._count_buy_order_in_cycle = count_buy_order_in_cycle
        self._count_sell_order_in_cycle = count_sell_order_in_cycle
        self._min_sell_price = min_sell_price
        self._max_buy_price = max_buy_price
        self._time_between_trades = time_between_trades

        # Переменные для управления состоянием стратегии
        self._state = "BUY"  # Возможные состояния: BUY, WAIT_AFTER_BUY, SELL, WAIT_AFTER_SELL
        self._buy_orders_executed = 0
        self._sell_orders_executed = 0
        self._cycle_count = 0
        self._last_state_change = 0.0
        self._last_trade_time = 0.0  # для задержки между отдельными ордерами

        # Флаг готовности подключения к маркету
        self._connector_ready = False

    def tick(self, timestamp: float):
        # Проверка готовности подключения к маркету
        if not self._connector_ready:
            self._connector_ready = self._market_info.market.ready
            if not self._connector_ready:
                self.logger().warning(f"{self._market_info.market.name} не готов. Ожидание подключения...")
                return
            else:
                self.logger().info(f"{self._market_info.market.name} готов. Старт торговли!")
                self._last_state_change = timestamp
                self._last_trade_time = timestamp

        # Получаем текущую рыночную цену (mid price)
        current_price = self._market_info.get_mid_price()

        if self._state == "BUY":
            # Проверяем, подходит ли цена для покупки
            if current_price > self._max_buy_price:
                self.logger().info(f"Текущая цена {current_price} выше максимально допустимой для покупки ({self._max_buy_price}). Ожидаем снижение цены.")
            else:
                if self._buy_orders_executed < self._count_buy_order_in_cycle:
                    # Проверяем задержку между ордерами
                    if timestamp - self._last_trade_time >= self._time_between_trades:
                        self.place_market_buy_order()
                        self._buy_orders_executed += 1
                        self._last_trade_time = timestamp
                    else:
                        self.logger().debug("Ожидание между ордерами на покупку...")
                else:
                    self.logger().info(f"Выполнено {self._buy_orders_executed} ордеров на покупку. Переход к ожиданию {self._time_after_buys} секунд.")
                    self._state = "WAIT_AFTER_BUY"
                    self._last_state_change = timestamp

        elif self._state == "WAIT_AFTER_BUY":
            # Ожидание после покупок
            if timestamp - self._last_state_change >= self._time_after_buys:
                self.logger().info("Время ожидания после покупок истекло. Переход к ордерам на продажу.")
                self._state = "SELL"
                self._last_trade_time = timestamp  # сбрасываем задержку между ордерами
            # Иначе продолжаем ожидание

        elif self._state == "SELL":
            # Проверяем, подходит ли цена для продажи
            if current_price < self._min_sell_price:
                self.logger().info(f"Текущая цена {current_price} ниже минимально допустимой для продажи ({self._min_sell_price}). Ожидаем рост цены.")
            else:
                if self._sell_orders_executed < self._count_sell_order_in_cycle:
                    # Проверяем задержку между ордерами
                    if timestamp - self._last_trade_time >= self._time_between_trades:
                        self.place_market_sell_order()
                        self._sell_orders_executed += 1
                        self._last_trade_time = timestamp
                    else:
                        self.logger().debug("Ожидание между ордерами на продажу...")
                else:
                    self.logger().info(f"Выполнено {self._sell_orders_executed} ордеров на продажу. Переход к ожиданию {self._time_after_sells} секунд.")
                    self._state = "WAIT_AFTER_SELL"
                    self._last_state_change = timestamp

        elif self._state == "WAIT_AFTER_SELL":
            # Ожидание после продаж
            if timestamp - self._last_state_change >= self._time_after_sells:
                self._cycle_count += 1
                self.logger().info(f"Завершён цикл №{self._cycle_count}.")
                # Если задано конечное число циклов и они выполнены, завершаем стратегию
                if self._total_rounds != -1 and self._cycle_count >= self._total_rounds:
                    self.logger().info("Достигнуто заданное количество циклов. Остановка стратегии.")
                    self.stop()
                    return

                # Сброс счетчиков и переход в состояние BUY для нового цикла
                self._buy_orders_executed = 0
                self._sell_orders_executed = 0
                self._state = "BUY"
                self._last_trade_time = timestamp  # сброс задержки между ордерами для нового цикла
            # Иначе продолжаем ожидание

    def place_market_buy_order(self):
        try:
            order_id = self.buy_with_specific_market(
                self._market_info,
                self._order_amount,
                OrderType.MARKET,
                Decimal("0")
            )
            self.logger().info(f"Размещён рыночный ордер на покупку, order_id: {order_id}")
        except Exception as e:
            self.logger().error(f"Ошибка при размещении ордера на покупку: {e}")

    def place_market_sell_order(self):
        try:
            order_id = self.sell_with_specific_market(
                self._market_info,
                self._order_amount,
                OrderType.MARKET,
                Decimal("0")
            )
            self.logger().info(f"Размещён рыночный ордер на продажу, order_id: {order_id}")
        except Exception as e:
            self.logger().error(f"Ошибка при размещении ордера на продажу: {e}")